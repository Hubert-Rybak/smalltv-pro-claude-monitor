from pathlib import Path
import importlib.util
import sys

ROOT = Path(__file__).resolve().parents[1]


def load_selector():
    path = ROOT / 'scripts/select_focus.py'
    assert path.is_file(), 'string-xref focus selector missing'
    spec = importlib.util.spec_from_file_location('select_focus', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_categories_include_actual_monitor_fields_and_not_total_false_positive():
    module = load_selector()
    assert 'monitor_http' in module.classify_string('/.sys/monitor.json')
    assert 'monitor_http' in module.classify_string('UP_CPU:')
    assert 'monitor_http' in module.classify_string('/monitor.html')
    assert 'monitor_http' not in module.classify_string('Total 17 bytes')
    assert 'filesystem_config' in module.classify_string('/.sys/app.json')
    assert 'ota' in module.classify_string('/update')
    assert 'ota' in module.classify_string('Update Success: %u\nRebooting...\n')
    assert 'ota' not in module.classify_string('update default trc: invalid ifx')
    assert 'app_ui' in module.classify_string('AppCtrl')


def test_focus_deduplicates_real_reference_function_identifiers():
    module = load_selector()
    rows = [
        {'address': '3f400020', 'text': '/monitor.html', 'code_references': [{'function': '400d1110'}, {'function': '400d1110'}]},
        {'address': '3f400100', 'text': '/.sys/config.json', 'code_references': [{'function': '400d2220'}, {'function': None}]},
        {'address': '3f400200', 'text': 'AppCtrl', 'code_references': [{'function': '400d3330'}]},
        {'address': '3f400300', 'text': '/update', 'code_references': [{'function': '400d4440'}]},
    ]
    result = module.select(rows)
    assert result['monitor_http']['functions'] == ['400d1110']
    assert result['filesystem_config']['functions'] == ['400d2220']
    assert result['app_ui']['functions'] == ['400d3330']
    assert result['ota']['functions'] == ['400d4440']
    assert result['monitor_http']['strings'][0]['address'] == '3f400020'
