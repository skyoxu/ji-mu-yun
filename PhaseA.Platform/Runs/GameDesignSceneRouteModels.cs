namespace PhaseA.Platform.Runs;

public sealed record GameDesignQuestionAnswer(
    string Id,
    string Label,
    string Answer,
    bool Required = false);

public sealed record GameDesignSceneRouteDraftRequest(
    string? Message,
    IReadOnlyList<GameDesignQuestionAnswer>? Answers = null,
    string? Model = null,
    GameDesignSceneRouteDocument? SceneRoute = null);

public sealed record GameDesignSceneRouteScene(
    string Id,
    string Name,
    string Role,
    bool M1Required,
    string PlayerGoal);

public sealed record GameDesignSceneRouteTransition(
    string From,
    string To,
    string Trigger,
    string ReturnsTo,
    IReadOnlyList<string> StateCarried);

public sealed record GameDesignSingleSceneConfirmation(
    bool Allowed,
    string Reason);

public sealed record GameDesignSceneRouteDocument(
    string SchemaVersion,
    string SceneCountIntent,
    string EntryScene,
    IReadOnlyList<GameDesignSceneRouteScene> Scenes,
    IReadOnlyList<GameDesignSceneRouteTransition> Transitions,
    GameDesignSingleSceneConfirmation SingleSceneConfirmation,
    IReadOnlyList<string> Notes);

public sealed record GameDesignSceneRouteDraftResult(
    string Status,
    string ProjectId,
    GameDesignSceneRouteDocument SceneRoute,
    string Source,
    string? FailureCode = null);
