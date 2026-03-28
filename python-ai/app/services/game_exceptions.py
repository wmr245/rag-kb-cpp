class GameValidationError(ValueError):
    pass


class GameNotFoundError(LookupError):
    pass


class GameConflictError(RuntimeError):
    pass
