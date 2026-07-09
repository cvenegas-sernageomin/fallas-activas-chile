"""Intenta descargar automáticamente todos los shapefiles de infraestructura crítica.

Si alguno falla, proporciona instrucciones para descarga manual.
"""
import sys
from pathlib import Path

# Importar los módulos de descarga
try:
    import descargar_carabineros
    import descargar_bomberos
    import descargar_puentes
    import descargar_educacion
except ImportError as e:
    print(f"❌ Error: {e}")
    print("   Ejecutar desde: fallas-activas-chile/tools/")
    sys.exit(1)


DESCARGAS = [
    ("Carabineros", descargar_carabineros.descargar_y_procesar),
    ("Bomberos", descargar_bomberos.descargar_y_procesar),
    ("Puentes", descargar_puentes.descargar_y_procesar),
    ("Educación", descargar_educacion.descargar_y_procesar),
]


def main():
    print("=" * 70)
    print("DESCARGANDO E INTEGRANDO CAPAS DE INFRAESTRUCTURA CRÍTICA")
    print("=" * 70)
    print()

    resultados = []
    errores = []

    for nombre, func in DESCARGAS:
        print(f"\n[{len(resultados) + 1}/{len(DESCARGAS)}] {nombre}...")
        print("-" * 70)
        try:
            count = func()
            resultados.append((nombre, count))
            print(f"✓ {nombre}: {count} registros convertidos")
        except FileNotFoundError as e:
            errores.append((nombre, str(e)))
            print(f"⚠️  {nombre}: Requiere descarga manual")
        except Exception as e:
            errores.append((nombre, str(e)))
            print(f"❌ {nombre}: Error inesperado")
            print(f"   {e}")

    # Resumen
    print("\n" + "=" * 70)
    print("RESUMEN")
    print("=" * 70)

    if resultados:
        print(f"\n✓ Completados ({len(resultados)}):")
        for nombre, count in resultados:
            print(f"  • {nombre}: {count:,} registros")

    if errores:
        print(f"\n⚠️  Requieren descarga manual ({len(errores)}):")
        for nombre, msg in errores:
            print(f"  • {nombre}: {msg[:60]}...")

    print("\n" + "=" * 70)
    if not errores:
        print("✓ Todas las capas procesadas correctamente.")
        print("\nPróximos pasos:")
        print("  1. Actualizar visor-web/index.html (LAYER_DEFS y SECTORES)")
        print("  2. Probar localmente: python -m http.server 8000")
        print("  3. Commit y desplegar a gh-pages")
    else:
        print(f"⚠️  Falta procesar {len(errores)} capa(s).")
        print("\nVer: fallas-activas-chile/DESCARGAR_CAPAS_NUEVAS.md")
        print("para instrucciones de descarga manual.")
    print("=" * 70)

    return 0 if not errores else 1


if __name__ == "__main__":
    sys.exit(main())
