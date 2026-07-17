using System.ComponentModel;
using System.Runtime.CompilerServices;

namespace JANIS.Desktop.Models;

public sealed class ChatMessage : INotifyPropertyChanged
{
    string _text = "";
    string? _imageUrl;

    public required string Role { get; init; }

    public required string Text
    {
        get => _text;
        set
        {
            if (_text == value) return;
            _text = value;
            OnPropertyChanged();
            // Estrai URL media dalla risposta se presente
            if (_imageUrl == null && !string.IsNullOrEmpty(value))
            {
                var extracted = ExtractMediaUrl(value);
                if (extracted != null)
                    ImageUrl = extracted;
            }
        }
    }

    public string? Badge { get; init; }

    public string? ImageUrl
    {
        get => _imageUrl;
        set
        {
            if (_imageUrl == value) return;
            _imageUrl = value;
            OnPropertyChanged();
            OnPropertyChanged(nameof(HasImage));
        }
    }

    public bool HasImage => !string.IsNullOrWhiteSpace(ImageUrl);

    public event PropertyChangedEventHandler? PropertyChanged;

    void OnPropertyChanged([CallerMemberName] string? name = null) =>
        PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(name));

    static string? ExtractMediaUrl(string text)
    {
        // URL: http://.../api/media/images/x.png
        var marker = "/api/media/images/";
        var idx = text.IndexOf(marker, StringComparison.OrdinalIgnoreCase);
        if (idx < 0) return null;
        var start = text.LastIndexOf("http", idx, StringComparison.OrdinalIgnoreCase);
        if (start < 0) return null;
        var end = start;
        while (end < text.Length && !char.IsWhiteSpace(text[end]) && text[end] is not ')' and not ']' and not '"')
            end++;
        var url = text[start..end].TrimEnd('.', ',', ';');
        return url.Contains(marker, StringComparison.OrdinalIgnoreCase) ? url : null;
    }
}

public enum AgentMode
{
    Janis,
    CursorAgent,
    CursorChat,
}
