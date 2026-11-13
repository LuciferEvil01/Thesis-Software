<?php
namespace local_alertatemprana;

/**
 * Cola de solicitudes de predicción (P12). La llenan el observador de calificaciones y el botón del
 * informe; la vacía el servicio de alerta.
 */
class requests {
    const GRADES = 'notas';
    const TEACHER = 'profesor';
    const PENDING = 0;
    const DONE = 1;

    /** Deja una solicitud, salvo que ya haya una pendiente del mismo motivo en el curso. */
    public static function enqueue(int $courseid, string $reason, ?int $userid = null): int {
        global $DB;
        $pending = $DB->get_record('local_alertatemprana_req',
            ['courseid' => $courseid, 'reason' => $reason, 'status' => self::PENDING], 'id', IGNORE_MULTIPLE);
        if ($pending) {
            return (int)$pending->id;
        }
        return (int)$DB->insert_record('local_alertatemprana_req', (object)['courseid' => $courseid,
            'reason' => $reason, 'userid' => $userid, 'status' => self::PENDING, 'timecreated' => time()]);
    }

    /** Solicitud pendiente más antigua del curso, si hay alguna. */
    public static function pending(int $courseid): ?\stdClass {
        global $DB;
        $records = $DB->get_records('local_alertatemprana_req', ['courseid' => $courseid, 'status' => self::PENDING],
            'timecreated ASC', '*', 0, 1);
        return $records ? reset($records) : null;
    }

    /** Última solicitud del profesor ya atendida, para mostrar su resultado. */
    public static function last_teacher_result(int $courseid): ?\stdClass {
        global $DB;
        $records = $DB->get_records('local_alertatemprana_req',
            ['courseid' => $courseid, 'reason' => self::TEACHER, 'status' => self::DONE], 'timeprocessed DESC', '*', 0, 1);
        return $records ? reset($records) : null;
    }
}
