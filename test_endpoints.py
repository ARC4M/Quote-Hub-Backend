#!/usr/bin/env python3
"""
Script de prueba para verificar los endpoints de carga masiva de productos.
"""
import requests
import json
import pandas as pd
from io import BytesIO

# Configuración
BASE_URL = "http://localhost:5000"  # Ajustar según tu configuración
TEST_EMAIL = "test@example.com"
TEST_PASSWORD = "testpassword123"


def test_endpoints():
    """Función principal para probar los endpoints"""

    # 1. Primero necesitamos un token de autenticación
    print("=== 1. Obteniendo token de autenticación ===")

    # Registrar empresa (si no existe)
    registro_data = {
        "nombre": "Empresa Test",
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD,
    }

    try:
        response = requests.post(f"{BASE_URL}/empresa/registro", json=registro_data)
        print(f"Registro: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Error en registro: {e}")

    # Login para obtener token
    login_data = {"email": TEST_EMAIL, "password": TEST_PASSWORD}

    try:
        response = requests.post(f"{BASE_URL}/empresa/login", json=login_data)
        if response.status_code == 200:
            token = response.json().get("token")
            print(f"Token obtenido: {token[:20]}...")
        else:
            print(f"Error en login: {response.status_code} - {response.text}")
            return
    except Exception as e:
        print(f"Error en login: {e}")
        return

    headers = {"Authorization": f"Bearer {token}"}

    # 2. Probar descarga de plantilla Excel
    print("\n=== 2. Probando descarga de plantilla Excel ===")

    try:
        response = requests.get(f"{BASE_URL}/producto/plantilla-excel", headers=headers)
        if response.status_code == 200:
            print("✓ Plantilla descargada exitosamente")
            # Guardar la plantilla para usar en la prueba
            with open("plantilla_test.xlsx", "wb") as f:
                f.write(response.content)
            print("✓ Plantilla guardada como 'plantilla_test.xlsx'")
        else:
            print(
                f"✗ Error descargando plantilla: {response.status_code} - {response.text}"
            )
    except Exception as e:
        print(f"✗ Error descargando plantilla: {e}")

    # 3. Crear archivo Excel de prueba
    print("\n=== 3. Creando archivo Excel de prueba ===")

    datos_prueba = {
        "nombre": ["Producto Test 1", "Producto Test 2", "Producto Test 3"],
        "descripcion": ["Descripción 1", "Descripción 2", "Descripción 3"],
        "precio": [100000, 250000, 75000],
        "unidad": ["unidad", "kg", "metro"],
        "codigo": ["TEST001", "TEST002", "TEST003"],
    }

    df = pd.DataFrame(datos_prueba)

    # Guardar en memoria
    excel_buffer = BytesIO()
    df.to_excel(excel_buffer, index=False, engine="openpyxl")
    excel_buffer.seek(0)

    print("✓ Archivo Excel de prueba creado")

    # 4. Probar carga masiva
    print("\n=== 4. Probando carga masiva de productos ===")

    try:
        files = {
            "archivo": (
                "productos_test.xlsx",
                excel_buffer.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        }

        response = requests.post(
            f"{BASE_URL}/producto/carga-masiva", files=files, headers=headers
        )

        if response.status_code == 200:
            resultado = response.json()
            print("✓ Carga masiva exitosa")
            print(f"  - Productos creados: {resultado.get('productos_creados', 0)}")
            print(
                f"  - Productos con errores: {resultado.get('productos_con_errores', 0)}"
            )

            if resultado.get("errores"):
                print("  - Errores encontrados:")
                for error in resultado["errores"]:
                    print(f"    Fila {error['fila']}: {error['error']}")
        else:
            print(f"✗ Error en carga masiva: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"✗ Error en carga masiva: {e}")

    # 5. Verificar productos creados
    print("\n=== 5. Verificando productos creados ===")

    try:
        response = requests.get(f"{BASE_URL}/producto", headers=headers)
        if response.status_code == 200:
            productos = response.json()
            print(f"✓ Total de productos: {len(productos)}")
            for producto in productos[-3:]:  # Mostrar últimos 3
                print(f"  - {producto['nombre']}: ${producto['precio']}")
        else:
            print(
                f"✗ Error obteniendo productos: {response.status_code} - {response.text}"
            )
    except Exception as e:
        print(f"✗ Error obteniendo productos: {e}")

    print("\n=== Pruebas completadas ===")


if __name__ == "__main__":
    test_endpoints()
