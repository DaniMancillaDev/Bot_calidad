from django.core.management.base import BaseCommand
from django.conf import settings
import json
from pathlib import Path
from calidad.models import RegistroDefecto, EvidenciaFotografica
from django.db.models import Count

class Command(BaseCommand):
    def handle(self, *args, **options):
        # Tomar ultimos 5 registros con evidencias v2
        registros_qs = RegistroDefecto.objects.annotate(v2_count=Count('evidencias_v2')).filter(v2_count__gt=0).order_by('-id')[:5]
        
        if not registros_qs:
            print("No hay registros con evidencias_v2")
            return
            
        # simular _parse_fotos_nums
        registros_data = []
        for r in registros_qs:
            nums = list(range(1, r.v2_count + 1))
            registros_data.append({
                'id': r.id,
                'user_id': r.user_id,
                'fotos_nums': nums,
                'v2_count': r.v2_count
            })
            
        print("Registros Data INICIAL:")
        print(json.dumps(registros_data, indent=2, default=str))

        evidencias_v2 = EvidenciaFotografica.objects.filter(registro_id__in=[r['id'] for r in registros_data])
        evs_por_registro = {}
        for ev in evidencias_v2:
            if ev.registro_id not in evs_por_registro:
                evs_por_registro[ev.registro_id] = []
            evs_por_registro[ev.registro_id].append(ev)
            
        fotos_en_disco = {}
        fotos_dir = Path(settings.MEDIA_ROOT) / 'fotos'
        
        for r in registros_data:
            actual_nums = []
            evs = evs_por_registro.get(r['id'], [])
            print(f"\nProcesando registro {r['id']} (user_id: {r['user_id']}) con {len(evs)} evidencias")
            
            user_id = r['user_id']
            user_folder = fotos_dir / str(user_id)
            print(f"user_folder: {user_folder}")
            print(f"user_folder exists? {user_folder.exists()}")
            
            for ev in evs:
                ev_path_str = ev.ruta_archivo
                if ev_path_str.startswith('media_files/'):
                    ev_path_str = ev_path_str[12:]
                elif ev_path_str.startswith('/media_files/'):
                    ev_path_str = ev_path_str[13:]
                ev_path_str = ev_path_str.lstrip('/')
                
                real_path = Path(settings.MEDIA_ROOT) / ev_path_str
                print(f" - ev {ev.id}: {real_path}")
                if real_path.exists():
                    import re
                    num = ev.id
                    m = re.match(r'^(\d+)_', real_path.name)
                    if m:
                        num = int(m.group(1))
                        
                    clave = f"{user_id}_{num}"
                    actual_nums.append(num)
                    
                    fotos_en_disco[clave] = {
                        'path': real_path,
                        'user_id': user_id,
                        'numero': num,
                        'evidencia': ev,
                        'es_legacy': False,
                        'ruta_rel': ev_path_str
                    }
                    print(f"   -> EXISTE. clave={clave}, num={num}")
                else:
                    print(f"   -> NO EXISTE EN DISCO.")
                    
            r['fotos_nums'] = sorted(list(set(actual_nums)))
            
        print("\nRegistros Data FINAL (lo que va al HTML):")
        print(json.dumps(registros_data, indent=2, default=str))
        

