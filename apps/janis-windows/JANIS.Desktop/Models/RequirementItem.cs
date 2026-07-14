namespace JANIS.Desktop.Models;

public enum RequirementState
{
    Unknown,
    Ok,
    Missing,
    Warning,
    Installing
}

public sealed class RequirementItem
{
    public required string Id { get; init; }
    public required string Name { get; init; }
    public required string Description { get; init; }
    public RequirementState State { get; set; } = RequirementState.Unknown;
    public string Detail { get; set; } = "";
    public string? InstallHint { get; init; }
    public bool CanAutoFix { get; init; }
}

public sealed class StackStatus
{
    public bool OllamaOnline { get; set; }
    public bool BrainOnline { get; set; }
    public bool WslAvailable { get; set; }
    public string Label { get; set; } = "OFFLINE";
    public string? Provider { get; set; }
    public string? OllamaModel { get; set; }
}
