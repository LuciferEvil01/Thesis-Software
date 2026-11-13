<?php
namespace local_alertatemprana\external;

use core_external\external_api;
use core_external\external_function_parameters;
use core_external\external_multiple_structure;
use core_external\external_single_structure;
use core_external\external_value;

/**
 * Nota de aprobado y rango de los ítems de módulo del libro de calificaciones de un curso (P16).
 *
 * Los servicios web estándar no devuelven la «calificación para aprobar» (gradepass), que hace
 * falta para convertir las notas en puntos a la escala del modelo.
 */
class get_gradeitems extends external_api {

    public static function execute_parameters(): external_function_parameters {
        return new external_function_parameters(['courseid' => new external_value(PARAM_INT, 'Id del curso')]);
    }

    public static function execute(int $courseid): array {
        global $DB;
        $p = self::validate_parameters(self::execute_parameters(), ['courseid' => $courseid]);
        $context = \context_course::instance($p['courseid']);
        self::validate_context($context);
        require_capability('local/alertatemprana:submit', $context);
        $sql = "SELECT gi.id, cm.id AS cmid, gi.itemmodule, gi.grademin, gi.grademax, gi.gradepass
                  FROM {grade_items} gi
                  JOIN {modules} m ON m.name = gi.itemmodule
                  JOIN {course_modules} cm ON cm.module = m.id AND cm.instance = gi.iteminstance AND cm.course = gi.courseid
                 WHERE gi.courseid = :courseid AND gi.itemtype = 'mod' AND gi.itemnumber = 0";
        $items = [];
        foreach ($DB->get_records_sql($sql, ['courseid' => $p['courseid']]) as $r) {
            $items[] = ['cmid' => (int)$r->cmid, 'module' => $r->itemmodule, 'grademin' => (float)$r->grademin,
                'grademax' => (float)$r->grademax, 'gradepass' => (float)$r->gradepass];
        }
        return $items;
    }

    public static function execute_returns(): external_multiple_structure {
        return new external_multiple_structure(new external_single_structure([
            'cmid' => new external_value(PARAM_INT, 'Id del módulo del curso'),
            'module' => new external_value(PARAM_PLUGIN, 'Tipo de módulo'),
            'grademin' => new external_value(PARAM_FLOAT, 'Nota mínima'),
            'grademax' => new external_value(PARAM_FLOAT, 'Nota máxima'),
            'gradepass' => new external_value(PARAM_FLOAT, 'Calificación para aprobar (0 = sin fijar)'),
        ]));
    }
}
