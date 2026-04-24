#!/usr/bin/env python3
"""
Runner de tests para KogniTerm.
Proporciona comandos convenientes para ejecutar tests.
"""

import subprocess
import sys
import os

def run_tests():
    """Ejecuta la suite completa de tests"""
    tests_dir = os.path.join(os.path.dirname(__file__), 'tests')
    cmd = [sys.executable, '-m', 'pytest', tests_dir, '-v']
    result = subprocess.run(cmd)
    sys.exit(result.returncode)

def run_unit_tests():
    """Ejecuta solo tests unitarios"""
    cmd = [sys.executable, '-m', 'pytest', 'tests/unit', '-v']
    result = subprocess.run(cmd)
    sys.exit(result.returncode)

def run_integration_tests():
    """Ejecuta solo tests de integración"""
    cmd = [sys.executable, '-m', 'pytest', 'tests/integration', '-v']
    result = subprocess.run(cmd)
    sys.exit(result.returncode)

if __name__ == '__main__':
    run_tests()
