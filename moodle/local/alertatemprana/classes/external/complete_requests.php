<?php
namespace local_alertatemprana\external;

use core_external\external_api;
use core_external\external_function_parameters;
use core_external\external_multiple_structure;
use core_external\external_single_structure;
use core_external\external_value;
use local_alertatemprana\requests;

/**
 * Marca como atendidas solicitudes de un curso, con el resultado que verá el profesor (P12).
 */
class complete_requests extends external_api {

    public static function execute_parameters(): external_function_parameters {
        return new external_function_parameters([
            'courseid' => new external_value(PARAM_INT, 'Id del curso'),
            'ids' => new external_multiple_structure(new external_value(PARAM_INT, 'Id de la solicitud')),
            'message' => new external_value(PARAM_TEXT, 'Resultado', VALUE_DEFAULT, ''),
        ]);
    }

    public static function execute(int $courseid, array $ids, string $message = ''): array {
        global $DB;
        $p = self::validate_parameters(self::execute_parameters(), compact('courseid', 'ids', 'message'));
        $context = \context_course::instance($p['courseid']);
        self::validate_context($context);
        require_capability('local/alertatemprana:submit', $context);
        $done = 0;
        $now = time();
        foreach ($p['ids'] as $id) {
            $r = $DB->get_record('local_alertatemprana_req', ['id' => $id, 'courseid' => $p['courseid']]);
            if ($r && (int)$r->status === requests::PENDING) {
                $DB->update_record('local_alertatemprana_req', (object)['id' => $r->id, 'status' => requests::DONE,
                    'message' => $p['message'], 'timeprocessed' => $now]);
                $done++;
            }
        }
        return ['completed' => $done];
    }

    public static function execute_returns(): external_single_structure {
        return new external_single_structure([
            'completed' => new external_value(PARAM_INT, 'Solicitudes marcadas como atendidas'),
        ]);
    }
}
