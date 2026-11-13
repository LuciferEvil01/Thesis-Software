<?php
namespace local_alertatemprana;

/**
 * Observadores del plugin.
 */
class observer {
    /**
     * Al calificar a un estudiante se pide al servicio que revise el curso (P12). El servicio decide
     * si alguna evaluación quedó completa; aquí solo se deja la solicitud, una por curso.
     */
    public static function user_graded(\core\event\user_graded $event): void {
        global $DB;
        if (!$event->courseid || !$DB->get_manager()->table_exists('local_alertatemprana_req')) {
            return;
        }
        requests::enqueue((int)$event->courseid, requests::GRADES);
    }

    /** Al borrar un curso se borran sus publicaciones, predicciones, acciones, solicitudes y configuración. */
    public static function course_deleted(\core\event\course_deleted $event): void {
        self::delete_course_data($event->objectid);
    }

    public static function delete_course_data(int $courseid): void {
        global $DB;
        $predids = $DB->get_fieldset_select('local_alertatemprana_pred', 'id', 'courseid = ?', [$courseid]);
        foreach (array_chunk($predids, 1000) as $chunk) {
            [$in, $params] = $DB->get_in_or_equal($chunk);
            $DB->delete_records_select('local_alertatemprana_act', "predictionid $in", $params);
        }
        $DB->delete_records('local_alertatemprana_pred', ['courseid' => $courseid]);
        $DB->delete_records('local_alertatemprana_run', ['courseid' => $courseid]);
        if ($DB->get_manager()->table_exists('local_alertatemprana_req')) {
            $DB->delete_records('local_alertatemprana_req', ['courseid' => $courseid]);
        }
        if ($DB->get_manager()->table_exists('local_alertatemprana_cfg')) {
            $DB->delete_records('local_alertatemprana_cfg', ['courseid' => $courseid]);
        }
    }
}
