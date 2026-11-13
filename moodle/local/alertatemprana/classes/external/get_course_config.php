<?php
namespace local_alertatemprana\external;

use core_external\external_api;
use core_external\external_function_parameters;
use core_external\external_multiple_structure;
use core_external\external_single_structure;
use core_external\external_value;
use local_alertatemprana\coursecfg;

/**
 * Tipos de evaluación que el profesor eligió para que el sistema analice su curso (P20).
 */
class get_course_config extends external_api {

    public static function execute_parameters(): external_function_parameters {
        return new external_function_parameters(['courseid' => new external_value(PARAM_INT, 'Id del curso')]);
    }

    public static function execute(int $courseid): array {
        $p = self::validate_parameters(self::execute_parameters(), ['courseid' => $courseid]);
        $context = \context_course::instance($p['courseid']);
        self::validate_context($context);
        require_capability('local/alertatemprana:submit', $context);
        return ['types' => coursecfg::types($p['courseid'])];
    }

    public static function execute_returns(): external_single_structure {
        return new external_single_structure([
            'types' => new external_multiple_structure(new external_value(PARAM_PLUGIN, 'Tipo de módulo')),
        ]);
    }
}
