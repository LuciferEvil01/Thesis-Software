<?php
namespace local_alertatemprana;

/**
 * Tipos de evaluación que el sistema analiza en cada curso (P20).
 *
 * Las tareas (`assign`) entran siempre: son las que disparan la predicción automática y equivalen a
 * las TMA con que se entrenó el modelo. El profesor puede añadir otros tipos calificables de su
 * curso; la predicción que él pide toma como referencia la evaluación más reciente con notas de
 * cualquiera de ellos. Solo pueden elegirse los tipos cuya fecha de cierre sabe leer el módulo de
 * predicción.
 */
class coursecfg {
    /** Tipos con fecha de cierre conocida: tarea (fecha de entrega) y cuestionario (cierre). */
    const DATED = ['assign', 'quiz'];
    const ALWAYS = 'assign';

    /** @return string[] tipos elegidos para el curso, con `assign` siempre */
    public static function types(int $courseid): array {
        global $DB;
        $saved = $DB->get_field('local_alertatemprana_cfg', 'types', ['courseid' => $courseid]);
        $types = array_filter(explode(',', (string)$saved));
        return array_values(array_unique(array_merge([self::ALWAYS], array_intersect($types, self::DATED))));
    }

    /** @param string[] $types */
    public static function save(int $courseid, array $types): void {
        global $DB;
        $types = array_values(array_unique(array_merge([self::ALWAYS], array_intersect($types, self::DATED))));
        $record = $DB->get_record('local_alertatemprana_cfg', ['courseid' => $courseid]);
        $data = ['courseid' => $courseid, 'types' => implode(',', $types), 'timemodified' => time()];
        if ($record) {
            $DB->update_record('local_alertatemprana_cfg', (object)(['id' => $record->id] + $data));
        } else {
            $DB->insert_record('local_alertatemprana_cfg', (object)$data);
        }
    }

    /**
     * Tipos de módulo calificables que tiene el curso, con cuántas actividades de cada uno.
     *
     * @return array tipo => número de actividades
     */
    public static function available(int $courseid): array {
        global $DB;
        $sql = "SELECT gi.itemmodule, COUNT(1) AS n
                  FROM {grade_items} gi
                 WHERE gi.courseid = :courseid AND gi.itemtype = 'mod' AND gi.itemnumber = 0
                       AND gi.gradetype > 0 AND gi.grademax > 0
              GROUP BY gi.itemmodule
              ORDER BY gi.itemmodule";
        return array_map('intval', $DB->get_records_sql_menu($sql, ['courseid' => $courseid]));
    }
}
