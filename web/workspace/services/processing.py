import os
import zipfile
import pandas as pd
from PIL import Image
from django.conf import settings
from workspace.models import ImportSession, DraftRegistro

def _extract_upload_files(session_uuid):
    zip_path = os.path.join(settings.MEDIA_ROOT, 'workspace', 'tmp', f"{session_uuid}.zip")
    extract_dir = os.path.join(settings.MEDIA_ROOT, 'workspace', 'sessions', str(session_uuid))
    photos_dir = os.path.join(extract_dir, 'photos')
    thumbs_dir = os.path.join(extract_dir, 'thumbs')
    
    os.makedirs(photos_dir, exist_ok=True)
    os.makedirs(thumbs_dir, exist_ok=True)
    
    excel_path = os.path.join(settings.MEDIA_ROOT, 'workspace', 'tmp', f"{session_uuid}_excel")
    if not os.path.exists(excel_path):
        excel_path = excel_path + ".csv" # fallback simple o buscar en carpeta
        
    found_excel = None
    for f in os.listdir(os.path.join(settings.MEDIA_ROOT, 'workspace', 'tmp')):
        if f.startswith(str(session_uuid)) and f.endswith(('.xls', '.xlsx', '.csv')) and not f.endswith('.zip'):
            found_excel = os.path.join(settings.MEDIA_ROOT, 'workspace', 'tmp', f)
            break
            
    if not found_excel:
        raise FileNotFoundError("Archivo Excel no encontrado.")
        
    return zip_path, found_excel, photos_dir, thumbs_dir

def _process_zip_contents(zip_path, photos_dir):
    extracted_images = []
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        for item in zip_ref.namelist():
            if not item.endswith('/'):
                filename = os.path.basename(item)
                if not filename:
                    continue
                    
                source = zip_ref.open(item)
                target_path = os.path.join(photos_dir, filename)
                
                # Manejar colisiones renombrando con sufijo
                base, ext = os.path.splitext(filename)
                counter = 1
                while os.path.exists(target_path):
                    filename = f"{base}_{counter}{ext}"
                    target_path = os.path.join(photos_dir, filename)
                    counter += 1
                    
                with open(target_path, "wb") as target:
                    target.write(source.read())
                    
                extracted_images.append((filename, target_path))
    return extracted_images

def _create_thumbnails(extracted_images, thumbs_dir):
    for filename, target_path in extracted_images:
        try:
            with Image.open(target_path) as img:
                img.thumbnail((300, 300))
                img.save(os.path.join(thumbs_dir, filename))
        except BaseException:
            pass # Si no es imagen o falla, ignorar

def _load_dataframe(found_excel):
    df = pd.read_excel(found_excel) if found_excel.endswith(('.xls', '.xlsx')) else pd.read_csv(found_excel)
    return df.astype(object).where(pd.notna(df), None)

def _create_draft_records(session, df, photos_dir):
    for idx, row in df.iterrows():
        row_index = idx + 1
        
        # Normalizar NaN/NaT a None para JSON
        raw_data = {k: (v if pd.notna(v) else None) for k, v in row.to_dict().items()}
        
        # Simple lowercase cleanup for mapped_data mapping
        mapped_data = {
            k.lower(): str(v) if pd.notna(v) else "" 
            for k, v in raw_data.items()
        }
        
        # Buscar fotos auto-match
        assigned_photos = []
        if 'foto' in mapped_data and mapped_data['foto']:
            fname = mapped_data['foto']
            if os.path.exists(os.path.join(photos_dir, fname)):
                assigned_photos.append(fname)
        
        DraftRegistro.objects.create(
            session=session,
            row_index=row_index,
            raw_data=raw_data,
            mapped_data=mapped_data,
            assigned_photos=assigned_photos,
            is_valid=False # Hasta que validen en API
        )

def process_upload_logic(session_uuid):
    session = ImportSession.objects.select_for_update().get(uuid=session_uuid)
    
    try:
        from django.db import transaction
        with transaction.atomic():
            zip_path, found_excel, photos_dir, thumbs_dir = _extract_upload_files(session_uuid)
            
            session.zip_extract_path = f"workspace/sessions/{session_uuid}"
            session.save(update_fields=['zip_extract_path'])

            images = _process_zip_contents(zip_path, photos_dir)
            _create_thumbnails(images, thumbs_dir)

            if os.path.exists(zip_path):
                os.remove(zip_path)

            dataframe = _load_dataframe(found_excel)
            
            session.total_rows = len(dataframe)
            session.save(update_fields=['total_rows'])
            
            _create_draft_records(session, dataframe, photos_dir)
                
            if os.path.exists(found_excel):
                os.remove(found_excel)
                
            session.status = 'DRAFT'
            session.save(update_fields=['status'])
        
    except Exception as e:
        session.status = 'FAILED'
        session.error_message = str(e)
        session.save(update_fields=['status', 'error_message'])
