<?php
namespace local_alertatemprana\external;

use core_external\external_api;
use core_external\external_function_parameters;
use core_external\external_multiple_structure;
use core_external\external_single_structure;
use core_external\external_value;

/**
 * Acciones de los profesores sobre las predicciones de un curso.
 */
class get_actions extends external_api {

    public static function execute_parameters(): external_function_parameters {
        return new external_function_parameters(['courseid' => new external_value(PARAM_INT, 'Id del curso')]);
    }

    public static function execute(int $courseid): array {
        global $DB;
        $p = self::validate_parameters(self::execute_parameters(), ['courseid' => $courseid]);
        $context = \context_course::instance($p['courseid']);
        self::validate_context($context);
        require_capability('local/alertatemprana:submit', $context);
        $sql = "SELECT a.id, r.cut, p.userid AS studentid, p.prediction, a.userid AS teacherid, a.actionname, a.timecreated
                  FROM {local_alertatemprana_act} a
                  JOIN {local_alertatemprana_pred} p ON p.id = a.predictionid
                  JOIN {local_alertatemprana_run} r ON r.id = p.runid
                 WHERE p.courseid = ?
              ORDER BY a.timecreated, a.id";
        return array_values(array_map(fn($r) => (array)$r, $DB->get_records_sql($sql, [$p['courseid']])));
    }

    public static function execute_returns(): external_multiple_structure {
        return new external_multiple_structure(new external_single_structure([
            'id' => new external_value(PARAM_INT, 'Id de la acción'),
            'cut' => new external_value(PARAM_ALPHA, 'Corte'),
            'studentid' => new external_value(PARAM_INT, 'Estudiante'),
            'prediction' => new external_value(PARAM_INT, '1 si estaba en riesgo académico'),
            'teacherid' => new external_value(PARAM_INT, 'Profesor'),
            'actionname' => new external_value(PARAM_ALPHANUMEXT, 'Acción'),
            'timecreated' => new external_value(PARAM_INT, 'Fecha'),
        ]));
    }
}
