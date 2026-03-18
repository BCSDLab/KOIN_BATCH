import importlib.util
import os

_parent_config = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'config.py')
_spec = importlib.util.spec_from_file_location('_central_config', _parent_config)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

for _name in dir(_mod):
    if not _name.startswith('_'):
        globals()[_name] = getattr(_mod, _name)
