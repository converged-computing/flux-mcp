from typing import Optional

from .registry import detect_transformer, get_transformer


def transform_jobspec(batch_job: str, to_format: str, from_format: Optional[str] = None):
    """
    Convert a batch jobspec from one format to another
    """

    # If no from transformer defined, try to detect
    try:
        from_format = from_format or detect_transformer(batch_job)
    except Exception as e:
        return {"status": "FAILURE", "error": str(e), "jobspec": None}

    # We are always converting to Flux from whatever
    try:
        from_transformer = get_transformer(from_format)
        to_transformer = get_transformer(to_format)
    except Exception as e:
        return {"status": "FAILURE", "error": str(e), "jobspec": None}

    try:
        normalized_jobspec = from_transformer.parse(batch_job)
        converted_jobspec = to_transformer.convert(normalized_jobspec)

    except Exception as e:
        return {"status": "FAILURE", "error": str(e), "jobspec": None}
    return {"status": "SUCCESS", "error": None, "jobspec": converted_jobspec}
