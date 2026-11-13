<?php
namespace local_alertatemprana\external;

use core_external\external_api;
use core_external\external_function_parameters;
use core_external\external_multiple_structure;
use core_external\external_single_structure;
use core_external\external_value;
use local_alertatemprana\notifier;
use local_alertatemprana\requests;

/**
 * Publica una predicción de un curso (P12: cuando una evaluación queda completa o cuando la pide el
 * profesor) y, si se indica, avisa a los profesores.
 */
class save_predictions extends external_api {

    public static function execute_parameters(): external_function_parameters {
        return new external_function_parameters([
            'courseid' => new external_value(PARAM_INT, 'Id del curso'),
            'cut' => new external_value(PARAM_ALPHA, 'Ajuste del modelo aplicado: first, mid o last'),
            'modelversion' => new external_value(PARAM_TEXT, 'Versión del modelo'),
            'threshold' => new external_value(PARAM_FLOAT, 'Umbral de la alerta'),
            'cutoffday' => new external_value(PARAM_INT, 'Día del curso de la predicción'),
            'timeend' => new external_value(PARAM_INT, 'Fin del periodo analizado (Unix)'),
            'anchorcmid' => new external_value(PARAM_INT, 'Evaluación de referencia', VALUE_DEFAULT, 0),
            'reason' => new external_value(PARAM_ALPHA, 'notas o profesor', VALUE_DEFAULT, requests::GRADES),
            'requestedby' => new external_value(PARAM_INT, 'Profesor que la pidió', VALUE_DEFAULT, 0),
            'info' => new external_value(PARAM_RAW, 'JSON con datos de la ejecución', VALUE_DEFAULT, ''),
            'notify' => new external_value(PARAM_BOOL, 'Avisar a los profesores', VALUE_DEFAULT, true),
            'predictions' => new external_multiple_structure(new external_single_structure([
                'userid' => new external_value(PARAM_INT, 'Estudiante'),
                'score' => new external_value(PARAM_FLOAT, 'Probabilidad estimada de riesgo académico'),
                'flagged' => new external_value(PARAM_BOOL, 'En riesgo académico (probabilidad > umbral)'),
                'calculations' => new external_value(PARAM_RAW, 'JSON: variables, valores y aportes'),
            ])),
        ]);
    }

    public static function execute(int $courseid, string $cut, string $modelversion, float $threshold, int $cutoffday,
            int $timeend, int $anchorcmid = 0, string $reason = requests::GRADES, int $requestedby = 0,
            string $info = '', bool $notify = true, array $predictions = []): array {
        global $DB;
        $p = self::validate_parameters(self::execute_parameters(), compact('courseid', 'cut', 'modelversion',
            'threshold', 'cutoffday', 'timeend', 'anchorcmid', 'reason', 'requestedby', 'info', 'notify', 'predictions'));
        if (!in_array($p['cut'], ['first', 'mid', 'last'], true)) {
            throw new \invalid_parameter_exception('ajuste del modelo desconocido: ' . $p['cut']);
        }
        if (!in_array($p['reason'], [requests::GRADES, requests::TEACHER], true)) {
            throw new \invalid_parameter_exception('motivo desconocido: ' . $p['reason']);
        }
        $course = get_course($p['courseid']);
        $context = \context_course::instance($course->id);
        self::validate_context($context);
        require_capability('local/alertatemprana:submit', $context);

        $students = get_enrolled_users($context, '', 0, 'u.id');
        $tx = $DB->start_delegated_transaction();
        $now = time();
        $run = (object)['courseid' => $course->id, 'cut' => $p['cut'], 'reason' => $p['reason'],
            'requestedby' => $p['requestedby'] ?: null, 'modelversion' => $p['modelversion'],
            'threshold' => $p['threshold'], 'cutoffday' => $p['cutoffday'], 'timeend' => $p['timeend'],
            'anchorcmid' => $p['anchorcmid'] ?: null, 'info' => $p['info'], 'timecreated' => $now];
        $run->id = $DB->insert_record('local_alertatemprana_run', $run);
        $flagged = 0;
        $rows = [];
        foreach ($p['predictions'] as $pred) {
            if (!isset($students[$pred['userid']])) {
                throw new \invalid_parameter_exception("el usuario {$pred['userid']} no está matriculado en el curso");
            }
            $flagged += (int)$pred['flagged'];
            $rows[] = (object)['runid' => $run->id, 'courseid' => $course->id, 'userid' => $pred['userid'],
                'prediction' => (int)$pred['flagged'], 'predictionscore' => $pred['score'],
                'calculations' => $pred['calculations'], 'timecreated' => $now];
        }
        $DB->insert_records('local_alertatemprana_pred', $rows);
        $tx->allow_commit();

        $notified = ($p['notify'] && $flagged > 0) ? notifier::notify($course, $run, $flagged, count($rows)) : 0;
        return ['runid' => $run->id, 'predictions' => count($rows), 'flagged' => $flagged, 'notified' => $notified];
    }

    public static function execute_returns(): external_single_structure {
        return new external_single_structure([
            'runid' => new external_value(PARAM_INT, 'Id de la publicación'),
            'predictions' => new external_value(PARAM_INT, 'Predicciones guardadas'),
            'flagged' => new external_value(PARAM_INT, 'Estudiantes en riesgo académico'),
            'notified' => new external_value(PARAM_INT, 'Profesores avisados'),
        ]);
    }
}
