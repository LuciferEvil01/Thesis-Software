<?php
namespace local_alertatemprana\external;

use core_external\external_api;
use core_external\external_function_parameters;
use core_external\external_multiple_structure;
use core_external\external_single_structure;
use core_external\external_value;
use local_alertatemprana\requests;

/**
 * Solicitudes de predicción pendientes en los cursos en que quien llama puede publicar (P12).
 */
class get_requests extends external_api {

    public static function execute_parameters(): external_function_parameters {
        return new external_function_parameters([]);
    }

    public static function execute(): array {
        global $DB;
        self::validate_context(\context_system::instance());
        $out = [];
        $records = $DB->get_records('local_alertatemprana_req', ['status' => requests::PENDING], 'timecreated ASC');
        foreach ($records as $r) {
            $context = \context_course::instance($r->courseid, IGNORE_MISSING);
            if (!$context || !has_capability('local/alertatemprana:submit', $context)) {
                continue;  // un curso que este servicio no regula
            }
            $out[] = ['id' => (int)$r->id, 'courseid' => (int)$r->courseid, 'reason' => $r->reason,
                'userid' => (int)$r->userid, 'timecreated' => (int)$r->timecreated];
        }
        return $out;
    }

    public static function execute_returns(): external_multiple_structure {
        return new external_multiple_structure(new external_single_structure([
            'id' => new external_value(PARAM_INT, 'Id de la solicitud'),
            'courseid' => new external_value(PARAM_INT, 'Id del curso'),
            'reason' => new external_value(PARAM_ALPHA, 'notas o profesor'),
            'userid' => new external_value(PARAM_INT, 'Profesor que la pidió (0 si es automática)'),
            'timecreated' => new external_value(PARAM_INT, 'Fecha de la solicitud'),
        ]));
    }
}
