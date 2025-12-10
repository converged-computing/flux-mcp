import flux_mcp.job as job
import flux_mcp.validate as validate

TOOLS = [
    validate.flux_validate_jobspec,
    validate.flux_count_jobspec_resources,
    job.handle_delegation,
]
