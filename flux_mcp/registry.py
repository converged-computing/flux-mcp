import flux_mcp.job as job
import flux_mcp.transformer as transform
import flux_mcp.validate as validate

TOOLS = [
    # Validation and counting
    validate.flux_validate_jobspec,
    validate.flux_count_jobspec_resources,
    # Job functions
    job.handle_delegation,
    transform.transform_jobspec,
    # Job core
    job.flux_submit_job,
    job.flux_cancel_job,
    job.flux_get_job_info,
]
