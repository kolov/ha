try:
    # For the linter
    from pyscript_types import state, service, task, log, state_trigger, time_trigger, pyscript
except ImportError:
    # When running in Jupyter
    pass

def list_switches():
    log.info("📋 Listing switches")
    for eid in state.names():
        if eid.startswith(("switch.")):
            attrs = state.get(eid, attribute="all")
            name = attrs.get("friendly_name", "(no name)")
            value = state.get(eid)
            log.info(f"→ {eid}: '{name}' [state: {value}]")
