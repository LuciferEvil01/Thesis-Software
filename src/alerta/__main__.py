"""Línea de comandos: `python -m alerta <orden>`.

    modelo importar-tesis       registra el modelo final de Proposal como v1 y lo activa
    modelo importar-e18         registra el modelo final con el umbral del Cap. 2 actual como v2 y
                                lo activa (P13)
    escala referencia CURSO ... grupo de referencia de la conversión de las notas: las notas de
                                aprobado de cursos cerrados de la plataforma (P16)
    modelo listar               versiones registradas y cuál está activa
    modelo activar VERSION      activa una versión (también para volver atrás)
    archivo sembrar-oulad       archiva los cursos de OULAD como cursos cerrados
    reentrenar [--no-activar]   reentrena si el archivo tiene periodos nuevos (para cron)
    ejecutar [--fecha AAAA-MM-DD] [--curso ID ...] [--todos] [--sin-aviso]
                                el servicio (cron cada 5 minutos): atiende las solicitudes de
                                predicción (notas completas o petición del profesor; P12)
    cursos                      cursos en que un profesor ha matriculado al servicio
    demo preparar [--con-servicio] | demo notas K | demo atender | demo estado
                                demostración con el curso AAA de OULAD (ver docs/DEMOSTRACION.md)
    validar-oulad [--curso C]   F5: reproduce un curso de OULAD en Moodle y compara de extremo a extremo
    validar-evea --tablas DIR   validación con cursos cerrados de EVEA (tablas de Moodle; protocolo E26)
    extraer CURSO [--registro ARCHIVO] [--tz ZONA]
                                extrae un curso de Moodle al esquema canónico (data/extracciones/);
                                con --registro, la actividad sale del registro exportado (fuente C)
"""

import argparse
import json
from pathlib import Path
import sys

import pandas as pd

from alerta import config
from alerta.archivo import Archivo
from alerta.modelo import importar
from alerta.modelo.reentrenamiento import Politica, retrain
from alerta.modelo.registro import Registro


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="alerta")
    sub = p.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("modelo").add_subparsers(dest="sub", required=True)
    m.add_parser("importar-tesis")
    m.add_parser("importar-e18")
    es = sub.add_parser("escala").add_subparsers(dest="sub", required=True)
    es.add_parser("referencia").add_argument("cursos", type=int, nargs="+")
    m.add_parser("listar")
    m.add_parser("activar").add_argument("version")
    a = sub.add_parser("archivo").add_subparsers(dest="sub", required=True)
    a.add_parser("sembrar-oulad").add_argument("--periodos", nargs="*")
    r = sub.add_parser("reentrenar")
    r.add_argument("--no-activar", action="store_true")
    ve = sub.add_parser("validar-evea", help="validación con cursos cerrados de EVEA (protocolo E26)")
    ve.add_argument("--tablas", type=Path, required=True, help="carpeta con un CSV por tabla de Moodle")
    ve.add_argument("--salida", type=Path, default=config.ROOT / "data" / "validacion_evea")
    ex = sub.add_parser("ejecutar")
    ex.add_argument("--fecha", help="simular la ejecución en esta fecha (AAAA-MM-DD); por defecto, ahora")
    ex.add_argument("--curso", type=int, nargs="*")
    ex.add_argument("--todos", action="store_true",
                    help="revisar todos los cursos aunque no tengan solicitudes (barrido o simulación)")
    ex.add_argument("--sin-aviso", action="store_true", help="publicar sin notificar a los profesores")
    sub.add_parser("cursos")
    dm = sub.add_parser("demo").add_subparsers(dest="sub", required=True)
    dm.add_parser("preparar").add_argument("--con-servicio", action="store_true")
    dm.add_parser("notas").add_argument("tarea", type=int, help="número de la tarea (1 = la primera)")
    dm.add_parser("atender")
    dm.add_parser("estado")
    sub.add_parser("validar-oulad").add_argument("--curso", default="AAA_2014J")
    e = sub.add_parser("extraer")
    e.add_argument("curso", type=int)
    e.add_argument("--registro", help="registro exportado de Moodle (CSV o Excel); por defecto, el plugin")
    e.add_argument("--tz", default="America/Havana", help="zona horaria del registro exportado")
    args = p.parse_args(argv)

    reg = Registro(config.MODELOS_DIR)
    if args.cmd == "modelo" and args.sub == "importar-tesis":
        reg.register(importar.from_proposal(config.PROPOSAL_DIR / "artifacts"))
        reg.activate("v1", "modelo final de la tesis (E14)")
        print("registrado y activado v1")
    elif args.cmd == "modelo" and args.sub == "importar-e18":
        from alerta.fuentes import oulad
        d, _ = oulad.load(config.OULAD_DIR)
        paquete = importar.from_proposal_e18(config.PROPOSAL_DIR / "artifacts", pd.read_parquet(config.TRAIN_DATASET), d,
                                             reg.next_version())
        reg.register(paquete)
        reg.activate(paquete.version, "modelo final con el umbral de E18 (proporción de desaprobados por corte)")
        print(f"registrado y activado {paquete.version}: umbrales "
              + ", ".join(f"{c} {m.threshold:.3f}" for c, m in paquete.cuts.items()))
    elif args.cmd == "escala":
        from alerta import calificacion
        from alerta.fuentes import moodle
        from alerta.moodle.cliente import Cliente
        c, parts = Cliente.desde_config(), []
        for course in args.cursos:
            d, _ = moodle.extract_course(c, course, calificacion=calificacion.ProporcionalOULAD())
            g = d.grades.merge(d.assessments[d.assessments["is_tma"]], on=["course_id", "item_id"])
            parts.append(g[["course_id", "grade", "grademin", "grademax", "gradepass"]])
        ref = calificacion.referencia(pd.concat(parts))
        path = calificacion.guardar_referencia(ref)
        print(json.dumps({k: {"cursos": v["cursos"], "aprobados": len(v["aprobados"])} for k, v in ref.items()},
                         ensure_ascii=False))
        print(f"guardado en {path}")
    elif args.cmd == "modelo" and args.sub == "listar":
        active = reg.active_version()
        for v in reg.versions():
            meta = reg.load(v).meta
            print(f"{'*' if v == active else ' '} {v}  {meta.get('creado', '-')}  periodos={meta.get('periodos')}")
    elif args.cmd == "modelo" and args.sub == "activar":
        reg.activate(args.version, "activación manual")
        print(f"activada {args.version}")
    elif args.cmd == "archivo":
        from alerta.fuentes import oulad
        d, labels = oulad.load(config.OULAD_DIR)
        done = oulad.archive(Archivo(config.ARCHIVO_DIR), d, labels, args.periodos)
        print(f"archivados {len(done)} cursos en {config.ARCHIVO_DIR}")
    elif args.cmd == "reentrenar":
        report = retrain(Archivo(config.ARCHIVO_DIR), reg, Politica(activar=not args.no_activar))
        print(json.dumps({k: report.get(k) for k in ("fecha", "campeon", "periodos_nuevos", "decision")},
                         ensure_ascii=False))
    elif args.cmd == "validar-oulad":
        from alerta.validacion import replay_oulad
        report = replay_oulad(args.curso)
        out = config.ROOT / "data" / "validacion" / f"{args.curso}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=1, ensure_ascii=False))
        print(("OK" if report["ok"] else "DIFERENCIAS") + f" · informe en {out}")
    elif args.cmd == "validar-evea":
        from alerta import validacion_evea
        validacion_evea.run(args.tablas, args.salida)
        print(f"informe en {args.salida}")
    elif args.cmd == "ejecutar":
        from datetime import datetime, timezone

        from alerta import servicio
        as_of = datetime.strptime(args.fecha, "%Y-%m-%d").replace(hour=12, tzinfo=timezone.utc) if args.fecha else None
        servicio.run(as_of, args.curso, everything=args.todos, notify=not args.sin_aviso)
    elif args.cmd == "demo":
        from alerta import demo
        if args.sub == "preparar":
            demo.prepare(args.con_servicio)
        elif args.sub == "notas":
            demo.grades(args.tarea)
        elif args.sub == "atender":
            demo.attend()
        demo.status()
    elif args.cmd == "cursos":
        from alerta.moodle import cursos
        from alerta.moodle.cliente import Cliente
        for c in cursos.discover(Cliente.desde_config()):
            profes = ", ".join(t["fullname"] for t in c["profesores"]) or "-"
            print(f"{c['id']:>5}  {c['shortname']:<28} rol={c['rol_servicio']:<15} profesores: {profes}")
    elif args.cmd == "extraer":
        from datetime import datetime

        from alerta.fuentes import moodle, registro_exportado
        from alerta.moodle.cliente import Cliente
        kwargs = {"activity": registro_exportado.source(args.registro, args.tz)} if args.registro else {}
        d, report = moodle.extract_course(Cliente.desde_config(), args.curso, **kwargs)
        out = config.ROOT / "data" / "extracciones" / str(args.curso) / datetime.now().strftime("%Y%m%d-%H%M%S")
        out.mkdir(parents=True)
        for name in ("courses", "students", "assessments", "grades", "activity"):
            getattr(d, name).to_parquet(out / f"{name}.parquet", index=False)
        report["fuente_actividad"] = "registro exportado" if args.registro else "plugin"
        (out / "informe.json").write_text(json.dumps(report, indent=1, ensure_ascii=False))
        print(json.dumps(report, ensure_ascii=False))
        print(f"guardado en {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
