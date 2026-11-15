<?php
namespace local_alertatemprana;

/**
 * Aviso en la página principal del curso (P22): el profesor ve el estado de la alerta temprana donde
 * ya trabaja, sin depender de la notificación por correo ni del menú del curso. Muestra la última
 * predicción (hasta qué fecha llegan sus datos, evaluación de referencia y estudiantes en riesgo), o que todavía no hay ninguna,
 * con los enlaces al informe y para pedir una predicción.
 */
class hook_callbacks {

    public static function course_banner(\core\hook\output\before_http_headers $hook): void {
        global $PAGE, $DB, $CFG;
        if (during_initial_install() || !str_starts_with((string)$PAGE->pagetype, 'course-view-')
                || empty($PAGE->course->id) || $PAGE->course->id == SITEID) {
            return;
        }
        $courseid = (int)$PAGE->course->id;
        $context = \context_course::instance($courseid);
        if (!has_capability('local/alertatemprana:view', $context)
                || !$DB->get_manager()->table_exists('local_alertatemprana_run')) {
            return;
        }
        require_once($CFG->dirroot . '/local/alertatemprana/lib.php');
        $report = new \moodle_url('/local/alertatemprana/index.php', ['id' => $courseid]);
        $request = new \moodle_url('/local/alertatemprana/request.php', ['id' => $courseid, 'sesskey' => sesskey()]);
        $runs = $DB->get_records('local_alertatemprana_run', ['courseid' => $courseid], 'timecreated DESC, id DESC', '*', 0, 1);
        if ($runs) {
            $run = reset($runs);
            $a = (object)[
                'date' => userdate($run->timeend, get_string('strftimedate')),
                'evaluation' => local_alertatemprana_anchor_name($run),
                'flagged' => $DB->count_records('local_alertatemprana_pred', ['runid' => $run->id, 'prediction' => 1]),
                'total' => $DB->count_records('local_alertatemprana_pred', ['runid' => $run->id]),
            ];
            $text = get_string('bannerlast', 'local_alertatemprana', $a);
        } else {
            $text = get_string('bannernone', 'local_alertatemprana');
        }
        if (requests::pending($courseid)) {
            $text .= ' ' . get_string('bannerpending', 'local_alertatemprana');
        }
        $html = \html_writer::tag('strong', get_string('report', 'local_alertatemprana')) . ' · ' . $text . ' '
            . \html_writer::link($report, get_string('bannerreport', 'local_alertatemprana'), ['class' => 'btn btn-sm btn-primary ms-2'])
            . \html_writer::link($request, get_string('requestnow', 'local_alertatemprana'), ['class' => 'btn btn-sm btn-secondary ms-1']);
        \core\notification::add($html, \core\output\notification::NOTIFY_INFO);
    }
}
