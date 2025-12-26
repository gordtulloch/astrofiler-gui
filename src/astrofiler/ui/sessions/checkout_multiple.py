def checkout_multiple_sessions(parent, session_items) -> None:
    from .checkout_workflow import checkout_multiple_sessions as _checkout

    return _checkout(parent, session_items)
