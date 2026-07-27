import ast
import glob
import collections

methods_to_check = {
    'DjangoUsuarioRepository': ['tiene_acceso', 'obtener', 'crear', 'actualizar', 'listar'],
    'DjangoRegistroRepository': ['guardar', 'obtener_todos', 'obtener_por_turno_depto', 'limpiar_por_usuario', 'obtener_estadisticas'],
    'DjangoContadorRepository': ['obtener_y_avanzar_lote', 'obtener_y_avanzar', 'obtener_actual'],
    'RedisConversationState': ['tiene_conversacion', 'obtener', 'iniciar', 'guardar', 'finalizar', 'persistir']
}

# we'll look for obj.method() calls.
# and track variable names initialized with these classes.

files = glob.glob('web/calidad/**/*.py', recursive=True) + glob.glob('shared/**/*.py', recursive=True)

for file in files:
    if 'venv' in file or '__pycache__' in file: continue
    
    with open(file, 'r') as f:
        try:
            tree = ast.parse(f.read())
        except:
            continue
    
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                attr_name = node.func.attr
                for cls, methods in methods_to_check.items():
                    if attr_name in methods:
                        # Print occurrences
                        print(f"{cls}.{attr_name} called in {file}: {getattr(node, 'lineno', '?')}")
