<?php
namespace local_alertatemprana\external;

use core_external\external_api;
use core_external\external_function_parameters;
use core_external\external_multiple_structure;
use core_external\external_single_structure;
use core_external\external_value;

/**
 * Actividad de los estudiantes de un curso (fuente A de PLAN.md, P3).
 *
 * Agrega `logstore_standard_log`: eventos de nivel educativo «participación», no anónimos, de
 * usuarios con un rol de arquetipo estudiante en el curso. Una fila por estudiante, día del curso
 * (día 0 = fecha de inicio; negativo = antes) y módulo (`cmid` = 0 si el evento no es de un módulo).
 * Es el equivalente de `studentVle` de OULAD (clics por estudiante, sitio y día).
 */
class get_activity extends external_api {

    public static function execute_parameters(): external_function_parameters {
        return new external_function_parameters([
            'courseid' => new external_value(PARAM_INT, 'Id del curso'),
            'timestart' => new external_value(PARAM_INT, 'Desde (Unix, incluido); 0 = sin límite', VALUE_DEFAULT, 0),
            'timeend' => new external_value(PARAM_INT, 'Hasta (Unix, excluido); 0 = sin límite', VALUE_DEFAULT, 0),
        ]);
    }

    public static function execute(int $courseid, int $timestart = 0, int $timeend = 0): array {
        global $DB;
        $params = self::validate_parameters(self::execute_parameters(),
            ['courseid' => $courseid, 'timestart' => $timestart, 'timeend' => $timeend]);
        $course = get_course($params['courseid']);
        $context = \context_course::instance($course->id);
        self::validate_context($context);
        require_capability('report/log:view', $context);

        $roles = array_keys(get_archetype_roles('student'));
        if (!$roles) {
            return ['courseid' => $course->id, 'startdate' => (int)$course->startdate, 'events' => []];
        }
        [$rolesql, $roleparams] = $DB->get_in_or_equal($roles, SQL_PARAMS_NAMED, 'role');
        $where = 'l.courseid = :courseid AND l.edulevel = :edulevel AND l.anonymous = 0';
        $sqlparams = ['courseid' => $course->id, 'edulevel' => \core\event\base::LEVEL_PARTICIPATING,
            'start' => (int)$course->startdate, 'ctx' => $context->id, 'modlevel' => CONTEXT_MODULE] + $roleparams;
        if ($params['timestart'] > 0) {
            $where .= ' AND l.timecreated >= :ts';
            $sqlparams['ts'] = $params['timestart'];
        }
        if ($params['timeend'] > 0) {
            $where .= ' AND l.timecreated < :te';
            $sqlparams['te'] = $params['timeend'];
        }
        $sql = "SELECT a.userid, a.day, a.cmid, COUNT(1) AS events
                  FROM (SELECT l.userid, FLOOR((l.timecreated - :start) / 86400.0) AS day,
                               CASE WHEN l.contextlevel = :modlevel THEN l.contextinstanceid ELSE 0 END AS cmid
                          FROM {logstore_standard_log} l
                         WHERE $where
                           AND EXISTS (SELECT 1 FROM {role_assignments} ra
                                        WHERE ra.userid = l.userid AND ra.contextid = :ctx AND ra.roleid $rolesql)) a
              GROUP BY a.userid, a.day, a.cmid";

        $events = [];
        $rs = $DB->get_recordset_sql($sql, $sqlparams);
        foreach ($rs as $r) {
            $events[] = ['userid' => (int)$r->userid, 'day' => (int)$r->day, 'cmid' => (int)$r->cmid,
                'events' => (int)$r->events];
        }
        $rs->close();
        return ['courseid' => $course->id, 'startdate' => (int)$course->startdate, 'events' => $events];
    }

    public static function execute_returns(): external_single_structure {
        return new external_single_structure([
            'courseid' => new external_value(PARAM_INT, 'Id del curso'),
            'startdate' => new external_value(PARAM_INT, 'Inicio del curso (Unix): día 0'),
            'events' => new external_multiple_structure(new external_single_structure([
                'userid' => new external_value(PARAM_INT, 'Id del estudiante'),
                'day' => new external_value(PARAM_INT, 'Día del curso'),
                'cmid' => new external_value(PARAM_INT, 'Módulo del curso; 0 si el evento no es de un módulo'),
                'events' => new external_value(PARAM_INT, 'Número de eventos'),
            ])),
        ]);
    }
}
