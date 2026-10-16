#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Test script for CQT fixes"""

from cqt.cqt_live_calc import calcular_cqt_topologia

# Test 1: Invalid type (should raise TypeError)
try:
    calcular_cqt_topologia('not a list')
    print('FAIL: Should raise TypeError')
except TypeError as e:
    print('PASS: TypeError caught:', str(e)[:50])

# Test 2: Negative potencia (should raise ValueError)
try:
    calcular_cqt_topologia([], potencia_trafo=-50)
    print('FAIL: Should raise ValueError')
except ValueError as e:
    print('PASS: ValueError caught:', str(e)[:50])

# Test 3: Valid empty list (should return empty result)
result = calcular_cqt_topologia([])
print('PASS: Empty list handled, pior_qt =', result['pior_qt'])

# Test 4: Valid trecho data
data = [{
    'letra': 'A',
    'montante': 'TRAFO',
    'comprimento_m': 100,
    'condutor': '3x50+1x50 - Al - F.P 1',
    'mono': 5,
    'bi': 0,
    'tri': 0
}]
result = calcular_cqt_topologia(data)
print('PASS: Valid data processed, pior_qt =', f'{result["pior_qt"]:.2f}%')
