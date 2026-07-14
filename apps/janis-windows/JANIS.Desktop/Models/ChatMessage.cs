namespace JANIS.Desktop.Models;

public sealed class ChatMessage
{
    public required string Role { get; init; }
    public required string Text { get; set; }
    public string? Badge { get; init; }
}

public enum AgentMode
{
    Janis,
    CursorAgent,
    CursorChat,
}
