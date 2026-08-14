import json
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from pydantic import ValidationError

from backend.app.api.dependencies import ImportHandlerDependency, SourceStagerDependency
from backend.app.application.handlers.imports import ImportMappingError
from backend.app.schemas.imports import ImportMappingRequest, ImportPreviewResponse, ImportResponse

router = APIRouter(prefix="/imports", tags=["imports"])


@router.post("/preview", response_model=ImportPreviewResponse)
async def preview(
    handler: ImportHandlerDependency,
    stager: SourceStagerDependency,
    file: Annotated[UploadFile, File(...)],
    sheet_name: Annotated[str | None, Form()] = None,
) -> ImportPreviewResponse:
    source = None
    try:
        source = await stager.stage_upload(file)
        result = handler.preview(source, sheet_name)
        return ImportPreviewResponse(
            columns=result.columns,
            total_rows=result.total_rows,
            suggested_mapping=result.suggested_mapping.as_dict(),
        )
    except (ValueError, ImportMappingError) as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    finally:
        if source is not None:
            source.path.unlink(missing_ok=True)


@router.post("", response_model=ImportResponse, status_code=status.HTTP_201_CREATED)
async def import_file(
    handler: ImportHandlerDependency,
    stager: SourceStagerDependency,
    file: Annotated[UploadFile, File(...)],
    mapping: Annotated[str, Form()] = "{}",
    sheet_name: Annotated[str | None, Form()] = None,
) -> ImportResponse:
    try:
        parsed_mapping = ImportMappingRequest.model_validate_json(mapping)
    except (ValidationError, ValueError, json.JSONDecodeError) as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="mapping 必须是 JSON 对象"
        ) from error
    source = None
    try:
        source = await stager.stage_upload(file)
        result = await handler.execute(source, parsed_mapping.as_mapping(), sheet_name)
        return ImportResponse(
            batch_id=result.batch_id,
            status=result.status,
            total_rows=result.total_rows,
            successful_rows=result.successful_rows,
            failed_rows=result.failed_rows,
            duplicate_rows=result.duplicate_rows,
            checkpoint_row=result.checkpoint_row,
            idempotent=result.idempotent,
        )
    except (ValueError, ImportMappingError) as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    finally:
        if source is not None:
            source.path.unlink(missing_ok=True)
