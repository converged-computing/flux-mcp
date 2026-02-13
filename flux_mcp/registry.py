import flux_mcp.job as job
import flux_mcp.resource as resource
import flux_mcp.sched as sched
import flux_mcp.transformer as transform
import flux_mcp.validate as validate

TOOLS = [
    # Resource listing
    resource.flux_resource_list,
    # Validation and counting
    validate.flux_validate_jobspec,
    validate.flux_count_jobspec_resources,
    validate.flux_validate_jobspec_persona,
    # Job functions
    job.flux_handle_delegation,
    transform.transform_jobspec,
    transform.transform_jobspec_persona,
    # Job core
    job.flux_submit_job,
    job.flux_cancel_job,
    job.flux_get_job_info,
    job.flux_get_job_logs,
    # Flux sched
    sched.flux_sched_init_graph,
    sched.flux_sched_partial_cancel,
    sched.flux_sched_cancel_job,
    sched.flux_sched_job_info,
    sched.flux_sched_match_allocate,
    # Flux sched queue / resource
    sched.flux_sched_qmanager_stats,
    sched.flux_sched_resource_allocate,
    sched.flux_sched_resource_allocate_orelse_reserve,
    sched.flux_sched_resource_allocate_with_satisfiability,
    sched.flux_sched_resource_feasibility_check,
    sched.flux_sched_resource_update,
    sched.flux_sched_resource_cancel,
    sched.flux_sched_resource_partial_cancel,
    sched.flux_sched_resource_find,
    sched.flux_sched_resource_set_property,
    sched.flux_sched_resource_remove_property,
    sched.flux_sched_resource_get_property,
    sched.flux_sched_resource_status,
    sched.flux_sched_resource_set_status,
    sched.flux_sched_resource_ns_info,
    sched.flux_sched_resource_stats,
    sched.flux_sched_resource_stats_clear,
    sched.flux_sched_resource_params,
    sched.flux_sched_resource_info,
]
