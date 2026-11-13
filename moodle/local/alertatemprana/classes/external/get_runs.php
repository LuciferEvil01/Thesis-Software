<?php
namespace local_alertatemprana\external;

use core_external\external_api;
use core_external\external_function_parameters;
use core_external\external_multiple_structure;
use core_external\external_single_structure;
use core_external\external_value;

/**
 * Predicciones ya publicadas de un curso, en orden de publicación (P12).
 */
class get_runs extends external_api {

    public static function execute_parameters(): external_function_parameters {
        return new external_function_parameters(['courseid' => new external_value(PARAM_INT, 'Id del curso')]);
    }

    public static function execute(int $courseid): array {
        global $DB;
        $p = self::validate_parameters(self::execute_parameters(), ['courseid' => $courseid]);
        $context = \context_course::instance($p['courseid']);
        self::validate_context($context);
        require_capability('local/alertatemprana:submit', $context);
        $runs = [];
        foreach ($DB->get_records('local_alertatemprana_run', ['courseid' => $p['courseid']], 'timecreated, id') as $r) {
            $runs[] = ['id' => (int)$r->id, 'cut' => $r->cut, 'reason' => $r->reason,
                'anchorcmid' => (int)$r->anchorcmid, 'modelversion' => $r->modelversion,
                'cutoffday' => (int)$r->cutoffday, 'timecreated' => (int)$r->timecreated,
                'predictions' => $DB->count_records('local_alertatemprana_pred', ['runid' => $r->id]),
                'flagged' => $DB->count_records('local_alertatemprana_pred', ['runid' => $r->id, 'prediction' => 1])];
        }
        return $runs;
    }

    public static function execute_returns(): external_multiple_structure {
        return new external_multiple_structure(new external_single_structure([
            'id' => new external_value(PARAM_INT, 'Id de la publicación'),
            'cut' => new external_value(PARAM_ALPHA, 'Ajuste del modelo aplicado'),
            'reason' => new external_value(PARAM_ALPHA, 'notas o profesor'),
            'anchorcmid' => new external_value(PARAM_INT, 'Evaluación de referencia'),
            'modelversion' => new external_value(PARAM_TEXT, 'Versión del modelo'),
            'cutoffday' => new external_value(PARAM_INT, 'Día del curso de la predicción'),
            'timecreated' => new external_value(PARAM_INT, 'Fecha de publicación'),
            'predictions' => new external_value(PARAM_INT, 'Predicciones'),
            'flagged' => new external_value(PARAM_INT, 'En riesgo académico'),
        ]));
    }
}
