<?php
namespace local_alertatemprana;

/**
 * Notificación a los profesores de un curso cuando una evaluación queda completa y la predicción
 * tiene estudiantes en riesgo (como insights_generator de Moodle Analytics; P12).
 */
class notifier {
    public static function notify(\stdClass $course, \stdClass $run, int $flagged, int $total): int {
        global $USER, $CFG;
        require_once($CFG->dirroot . '/local/alertatemprana/lib.php');
        $context = \context_course::instance($course->id);
        $url = new \moodle_url('/local/alertatemprana/index.php', ['id' => $course->id, 'runid' => $run->id]);
        $sent = 0;
        foreach (get_enrolled_users($context, 'local/alertatemprana:view') as $teacher) {
            if ($teacher->id == $USER->id) {
                continue;  // el usuario de servicio
            }
            $a = (object)['course' => format_string($course->fullname, true, ['context' => $context]),
                'evaluation' => local_alertatemprana_anchor_name($run), 'flagged' => $flagged,
                'total' => $total, 'firstname' => $teacher->firstname, 'url' => $url->out(false)];
            $message = new \core\message\message();
            $message->component = 'local_alertatemprana';
            $message->name = 'alerta';
            $message->userfrom = \core_user::get_noreply_user();
            $message->userto = $teacher;
            $message->subject = get_string('notification_subject', 'local_alertatemprana', $a);
            $message->fullmessage = get_string('notification_body', 'local_alertatemprana', $a);
            $message->fullmessageformat = FORMAT_PLAIN;
            $message->fullmessagehtml = get_string('notification_html', 'local_alertatemprana', $a);
            $message->smallmessage = get_string('notification_subject', 'local_alertatemprana', $a);
            $message->notification = 1;
            $message->contexturl = $url->out(false);
            $message->contexturlname = get_string('report', 'local_alertatemprana');
            $message->courseid = $course->id;
            if (message_send($message)) {
                $sent++;
            }
        }
        return $sent;
    }
}
