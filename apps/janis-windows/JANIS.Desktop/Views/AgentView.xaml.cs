using System.Collections.ObjectModel;
using System.Text.Json;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using JANIS.Desktop.Models;
using JANIS.Desktop.Services;

namespace JANIS.Desktop.Views;

public partial class AgentView : UserControl
{
    readonly JanisBrainClient _brain = new();
    readonly ObservableCollection<ChatMessage> _messages = new();
    CancellationTokenSource? _cts;
    ChatMessage? _streamMsg;

    public AgentView()
    {
        InitializeComponent();
        MsgList.ItemsSource = _messages;
        Loaded += async (_, _) => await RefreshCursorStatusAsync();
    }

    async Task RefreshCursorStatusAsync()
    {
        var st = await _brain.GetCursorStatusAsync();
        if (st == null)
        {
            CursorStatus.Text = "Brain offline";
            return;
        }
        var root = st.Value;
        var key = root.TryGetProperty("cursor_api_configured", out var k) && k.GetBoolean();
        var ready = root.TryGetProperty("ready", out var r) && r.GetBoolean();
        CursorStatus.Text = ready ? "Cursor API · PRONTO"
            : key ? "Cursor API · abilita PRO in impostazioni"
            : "Cursor API · chiave mancante";
    }

    void Append(string role, string text, string? badge = null)
    {
        _messages.Add(new ChatMessage { Role = role, Text = text, Badge = badge });
        MsgScroll.ScrollToEnd();
    }

    async void Send_Click(object sender, RoutedEventArgs e) => await SendAsync();

    async void InputBox_KeyDown(object sender, KeyEventArgs e)
    {
        if (e.Key == Key.Enter && Keyboard.Modifiers == ModifierKeys.Control)
        {
            e.Handled = true;
            await SendAsync();
        }
    }

    async Task SendAsync()
    {
        var text = InputBox.Text.Trim();
        if (text.Length == 0) return;
        InputBox.Clear();
        SendBtn.IsEnabled = false;

        var mode = ModeCombo.SelectedIndex switch
        {
            1 => AgentMode.CursorAgent,
            2 => AgentMode.CursorChat,
            _ => AgentMode.Janis,
        };

        Append("user", text);
        _streamMsg = new ChatMessage { Role = "assistant", Text = "…", Badge = mode.ToString() };
        _messages.Add(_streamMsg);
        _cts?.Cancel();
        _cts = new CancellationTokenSource();

        try
        {
            if (mode == AgentMode.Janis)
                await RunJanisAsync(text, _cts.Token);
            else if (mode == AgentMode.CursorAgent)
                await RunCursorAgentAsync(text, _cts.Token);
            else
                await RunCursorChatAsync(text, _cts.Token);
        }
        catch (Exception ex)
        {
            if (_streamMsg != null) _streamMsg.Text = "Errore: " + ex.Message;
        }
        finally
        {
            SendBtn.IsEnabled = true;
            _streamMsg = null;
            MsgScroll.ScrollToEnd();
        }
    }

    async Task RunJanisAsync(string text, CancellationToken ct)
    {
        var buf = "";
        await _brain.StreamJanisWebSocketAsync(text, ev =>
        {
            Dispatcher.Invoke(() =>
            {
                var t = ev.TryGetProperty("type", out var tp) ? tp.GetString() : "";
                if (t == "chat_chunk" && ev.TryGetProperty("text", out var tx))
                {
                    buf += tx.GetString();
                    if (_streamMsg != null) _streamMsg.Text = buf;
                }
                if (t == "media_image" && ev.TryGetProperty("url", out var iu))
                {
                    var url = iu.GetString();
                    if (_streamMsg != null && !string.IsNullOrWhiteSpace(url))
                        _streamMsg.ImageUrl = url;
                    Append("media", url ?? "", "image");
                }
                if (t == "state" && ev.TryGetProperty("state", out var st))
                    Append("sys", st.GetString() ?? "", "state");
                if (t == "tool_start")
                    Append("tool", $"▸ {ev.GetProperty("tool")}", "tool");
            });
        }, ct);
        if (_streamMsg != null && string.IsNullOrWhiteSpace(buf))
            _streamMsg.Text = "(nessuna risposta)";
    }

    async Task RunCursorAgentAsync(string text, CancellationToken ct)
    {
        var buf = "";
        await _brain.StreamSsePostAsync("/api/cursor/agent", new { prompt = text }, ev =>
        {
            Dispatcher.Invoke(() => ProcessCursorEvent(ev, ref buf));
        }, ct);
    }

    async Task RunCursorChatAsync(string text, CancellationToken ct)
    {
        var buf = "";
        await _brain.StreamSsePostAsync("/api/cursor/chat", new { text }, ev =>
        {
            Dispatcher.Invoke(() =>
            {
                var t = ev.TryGetProperty("type", out var tp) ? tp.GetString() : "";
                if (t == "chat_chunk" && ev.TryGetProperty("text", out var tx))
                {
                    buf += tx.GetString();
                    if (_streamMsg != null) _streamMsg.Text = buf;
                }
                else
                    ProcessCursorEvent(ev, ref buf);
            });
        }, ct);
    }

    void ProcessCursorEvent(JsonElement ev, ref string buf)
    {
        var t = ev.TryGetProperty("type", out var tp) ? tp.GetString() : "";
        if (t == "cursor_stream" && ev.TryGetProperty("chunk", out var ch))
        {
            buf += ch.GetString();
            if (_streamMsg != null) _streamMsg.Text = buf;
        }
        if (t == "final" && ev.TryGetProperty("text", out var fin))
        {
            buf = fin.GetString() ?? buf;
            if (_streamMsg != null) _streamMsg.Text = buf;
        }
        if (t == "error")
            if (_streamMsg != null)
                _streamMsg.Text = ev.TryGetProperty("message", out var m) ? m.GetString() : "Errore Cursor";
    }

    async void EnableCursor_Click(object sender, RoutedEventArgs e)
    {
        var key = CursorKeyBox.Password.Trim();
        if (key.Length > 0)
            await _brain.SaveCursorKeyAsync(key, CursorModelBox.Text.Trim());
        await _brain.EnableCursorAsync();
        await RefreshCursorStatusAsync();
        Append("sys", "Cursor PRO abilitato — reasoning + agent code", "config");
    }
}
