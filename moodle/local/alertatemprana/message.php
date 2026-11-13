<?php
// Mensaje del profesor a los estudiantes seleccionados en el informe (acción en lote «Enviar mensaje»).
require_once(__DIR__ . '/../../config.php');
require_once($CFG->dirroot . '/message/lib.php');

use local_alertatemprana\actions;

$courseid = required_param('id', PARAM_INT);
$runid = optional_param('runid', 0, PARAM_INT);
$ids = optional_param_array('predictionids', [], PARAM_INT);
$text = optional_param('text', '', PARAM_RAW);
$course = get_course($courseid);
require_login($course);
require_sesskey();
$context = context_course::instance($course->id);
require_capability('local/alertatemprana:view', $context);
require_capability('moodle/site:sendmessage', context_system::instance());
$back = new moodle_url('/local/alertatemprana/index.php', ['id' => $course->id, 'runid' => $runid]);
if (!$ids) {
    redirect($back, get_string('noneselected', 'local_alertatemprana'), null, \core\output\notification::NOTIFY_WARNING);
}
[$in, $params] = $DB->get_in_or_equal($ids);
$preds = $DB->get_records_select('local_alertatemprana_pred', "id $in AND courseid = ?", array_merge($params, [$course->id]));

if (trim($text) !== '') {
    foreach ($preds as $p) {
        message_post_message($USER, core_user::get_user($p->userid), $text, FORMAT_PLAIN);
        actions::record($p->id, $USER->id, actions::SEND_MESSAGE);
    }
    redirect($back, get_string('messagessent', 'local_alertatemprana', count($preds)), null,
        \core\output\notification::NOTIFY_SUCCESS);
}

$PAGE->set_url(new moodle_url('/local/alertatemprana/message.php', ['id' => $course->id, 'runid' => $runid]));
$PAGE->set_context($context);
$PAGE->set_pagelayout('report');
$PAGE->set_title(get_string('messageselected', 'local_alertatemprana'));
$PAGE->set_heading(format_string($course->fullname));
echo $OUTPUT->header();
echo $OUTPUT->heading(get_string('messageselected', 'local_alertatemprana'));
$names = array_map(fn($p) => fullname(core_user::get_user($p->userid)), $preds);
echo html_writer::tag('p', get_string('messageto', 'local_alertatemprana', implode(', ', $names)));
echo html_writer::start_tag('form', ['method' => 'post']);
foreach (['id' => $course->id, 'runid' => $runid, 'sesskey' => sesskey()] as $k => $v) {
    echo html_writer::empty_tag('input', ['type' => 'hidden', 'name' => $k, 'value' => $v]);
}
foreach ($ids as $pid) {
    echo html_writer::empty_tag('input', ['type' => 'hidden', 'name' => 'predictionids[]', 'value' => $pid]);
}
echo html_writer::tag('textarea', '', ['name' => 'text', 'rows' => 6, 'class' => 'form-control mb-2', 'required' => 'required']);
echo html_writer::tag('button', get_string('send', 'message'), ['type' => 'submit', 'class' => 'btn btn-primary']);
echo ' ' . html_writer::link($back, get_string('cancel'), ['class' => 'btn btn-secondary']);
echo html_writer::end_tag('form');
echo $OUTPUT->footer();
