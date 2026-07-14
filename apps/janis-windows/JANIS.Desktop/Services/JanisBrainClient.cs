using System.IO;
using System.Net.Http;
using System.Net.Http.Json;
using System.Net.WebSockets;
using System.Text;
using System.Text.Json;
using JANIS.Desktop.Models;

namespace JANIS.Desktop.Services;

public sealed class JanisBrainClient
{
    readonly HttpClient _http = new() { Timeout = TimeSpan.FromMinutes(15) };

    public async Task<StackStatus> GetStatusAsync(CancellationToken ct = default)
    {
        var status = new StackStatus();
        try
        {
            using var r = await _http.GetAsync($"{JanisPaths.BrainUrl}/api/status", ct);
            if (!r.IsSuccessStatusCode) return status;
            var json = await r.Content.ReadFromJsonAsync<JsonElement>(ct);
            status.BrainOnline = json.GetProperty("service").GetString() == "JANIS";
            status.Provider = json.TryGetProperty("reasoning_provider", out var p) ? p.GetString() : null;
            if (json.TryGetProperty("ollama", out var o))
                status.OllamaOnline = o.TryGetProperty("online", out var on) && on.GetBoolean();
        }
        catch { /* offline */ }

        status.WslAvailable = StackOrchestrator.IsWslInstalled();
        status.Label = status.BrainOnline && status.OllamaOnline ? "ONLINE"
            : status.BrainOnline ? "BRAIN OK"
            : status.OllamaOnline ? "OLLAMA OK" : "OFFLINE";
        return status;
    }

    public async Task<JsonElement?> GetCursorStatusAsync(CancellationToken ct = default)
    {
        try
        {
            using var r = await _http.GetAsync($"{JanisPaths.BrainUrl}/api/cursor/status", ct);
            if (!r.IsSuccessStatusCode) return null;
            return await r.Content.ReadFromJsonAsync<JsonElement>(ct);
        }
        catch
        {
            return null;
        }
    }

    public async Task<bool> SaveCursorKeyAsync(string apiKey, string? model = null, CancellationToken ct = default)
    {
        var body = new Dictionary<string, string?> { ["cursor_api_key"] = apiKey };
        if (!string.IsNullOrWhiteSpace(model))
            body["cursor_model"] = model;
        using var content = new StringContent(JsonSerializer.Serialize(body), Encoding.UTF8, "application/json");
        using var r = await _http.PostAsync($"{JanisPaths.BrainUrl}/api/settings", content, ct);
        return r.IsSuccessStatusCode;
    }

    public async Task<bool> EnableCursorAsync(CancellationToken ct = default)
    {
        var body = new
        {
            paid_mode = true,
            cursor_code_enabled = true,
            reasoning_provider = "cursor",
        };
        using var content = new StringContent(JsonSerializer.Serialize(body), Encoding.UTF8, "application/json");
        using var r = await _http.PostAsync($"{JanisPaths.BrainUrl}/api/runtime", content, ct);
        return r.IsSuccessStatusCode;
    }

    public async Task<string> RunTerminalAsync(string command, string shell = "wsl", CancellationToken ct = default)
    {
        var payload = new { command, shell };
        using var content = new StringContent(JsonSerializer.Serialize(payload), Encoding.UTF8, "application/json");
        using var r = await _http.PostAsync($"{JanisPaths.BrainUrl}/api/hud/terminal", content, ct);
        var body = await r.Content.ReadAsStringAsync(ct);
        if (!r.IsSuccessStatusCode) return $"HTTP {(int)r.StatusCode}: {body}";
        using var doc = JsonDocument.Parse(body);
        if (doc.RootElement.TryGetProperty("ok", out var ok) && ok.GetBoolean())
            return doc.RootElement.GetProperty("output").GetString() ?? "";
        return doc.RootElement.TryGetProperty("error", out var err) ? err.GetString() ?? body : body;
    }

    public async Task<string?> GetRuntimeJsonAsync(CancellationToken ct = default)
    {
        try
        {
            return await _http.GetStringAsync($"{JanisPaths.BrainUrl}/api/runtime", ct);
        }
        catch
        {
            return null;
        }
    }

    public async Task<string?> GetActiveToolsAsync(CancellationToken ct = default)
    {
        try
        {
            using var r = await _http.GetAsync($"{JanisPaths.BrainUrl}/api/hud/dashboard", ct);
            if (!r.IsSuccessStatusCode) return null;
            var json = await r.Content.ReadFromJsonAsync<JsonElement>(ct);
            if (json.TryGetProperty("tools_active", out var tools))
                return tools.ToString();
        }
        catch { }
        return null;
    }

    public async Task StreamJanisWebSocketAsync(
        string text,
        Action<JsonElement> onEvent,
        CancellationToken ct = default)
    {
        using var ws = new ClientWebSocket();
        var uri = new Uri(JanisPaths.ChatWsUrl);
        await ws.ConnectAsync(uri, ct);
        var send = JsonSerializer.Serialize(new { type = "chat", text, device_id = "janis-desktop" });
        await ws.SendAsync(Encoding.UTF8.GetBytes(send), WebSocketMessageType.Text, true, ct);

        var buf = new byte[8192];
        var acc = new StringBuilder();
        while (ws.State == WebSocketState.Open && !ct.IsCancellationRequested)
        {
            acc.Clear();
            WebSocketReceiveResult res;
            do
            {
                res = await ws.ReceiveAsync(buf, ct);
                if (res.MessageType == WebSocketMessageType.Close) return;
                acc.Append(Encoding.UTF8.GetString(buf, 0, res.Count));
            } while (!res.EndOfMessage);

            try
            {
                onEvent(JsonDocument.Parse(acc.ToString()).RootElement);
            }
            catch { /* skip */ }
        }
    }

    public async Task StreamSsePostAsync(
        string path,
        object body,
        Action<JsonElement> onEvent,
        CancellationToken ct = default)
    {
        using var req = new HttpRequestMessage(HttpMethod.Post, $"{JanisPaths.BrainUrl}{path}");
        req.Headers.Add("Accept", "text/event-stream");
        req.Content = new StringContent(JsonSerializer.Serialize(body), Encoding.UTF8, "application/json");
        using var resp = await _http.SendAsync(req, HttpCompletionOption.ResponseHeadersRead, ct);
        resp.EnsureSuccessStatusCode();
        await using var stream = await resp.Content.ReadAsStreamAsync(ct);
        using var reader = new StreamReader(stream);
        while (!reader.EndOfStream && !ct.IsCancellationRequested)
        {
            var line = await reader.ReadLineAsync(ct);
            if (line == null) break;
            if (!line.StartsWith("data: ", StringComparison.Ordinal)) continue;
            var json = line["data: ".Length..];
            if (string.IsNullOrWhiteSpace(json)) continue;
            try
            {
                onEvent(JsonDocument.Parse(json).RootElement);
            }
            catch { /* skip */ }
        }
    }
}
