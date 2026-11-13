<?php
namespace local_alertatemprana;

/**
 * Acciones de un profesor sobre una predicción. Son las de Moodle Analytics (core_analytics\prediction)
 * y quedan guardadas para el futuro mecanismo de aceptación de recomendaciones.
 */
class actions {
    /** Aceptar: el profesor toma la alerta y actúa. */
    const FIXED = 'fixed';
    /** No aplicable al estudiante. */
    const NOT_APPLICABLE = 'notapplicable';
    /** La alerta es incorrecta: el estudiante no está en riesgo. */
    const INCORRECTLY_FLAGGED = 'incorrectlyflagged';
    const USEFUL = 'useful';
    const NOT_USEFUL = 'notuseful';
    /** Se registran solas al usarlas desde el informe. */
    const VIEW_DETAILS = 'predictiondetails';
    const SEND_MESSAGE = 'sendmessage';

    /** Acciones que fijan el estado de una alerta (botones del informe). */
    const STATUS = [self::FIXED, self::NOT_APPLICABLE, self::INCORRECTLY_FLAGGED, self::USEFUL, self::NOT_USEFUL];
    const ALL = [self::FIXED, self::NOT_APPLICABLE, self::INCORRECTLY_FLAGGED, self::USEFUL, self::NOT_USEFUL,
        self::VIEW_DETAILS, self::SEND_MESSAGE];

    public static function record(int $predictionid, int $userid, string $action): void {
        global $DB;
        if (!in_array($action, self::ALL, true)) {
            throw new \coding_exception("acción desconocida: {$action}");
        }
        $DB->insert_record('local_alertatemprana_act', (object)['predictionid' => $predictionid, 'userid' => $userid,
            'actionname' => $action, 'timecreated' => time()]);
    }

    /** Último estado (acción de STATUS) de cada predicción: predictionid → acción. */
    public static function latest_status(array $predictionids): array {
        global $DB;
        if (!$predictionids) {
            return [];
        }
        [$in, $params] = $DB->get_in_or_equal($predictionids);
        [$st, $stparams] = $DB->get_in_or_equal(self::STATUS);
        $rows = $DB->get_records_select('local_alertatemprana_act', "predictionid $in AND actionname $st",
            array_merge($params, $stparams), 'timecreated ASC, id ASC', 'id, predictionid, actionname');
        $out = [];
        foreach ($rows as $r) {
            $out[$r->predictionid] = $r->actionname;
        }
        return $out;
    }
}
