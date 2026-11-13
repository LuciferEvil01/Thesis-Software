<?php
// Evaluaciones que el sistema analiza en un curso (P20): el profesor ve los tipos calificables de su
// curso y elige cuáles entran, además de las tareas.
require_once(__DIR__ . '/../../config.php');

use local_alertatemprana\coursecfg;

$courseid = required_param('id', PARAM_INT);
$course = get_course($courseid);
require_login($course);
$context = context_course::instance($course->id);
require_capability('local/alertatemprana:view', $context);

$url = new moodle_url('/local/alertatemprana/evaluations.php', ['id' => $course->id]);
$report = new moodle_url('/local/alertatemprana/index.php', ['id' => $course->id]);
if (data_submitted() && confirm_sesskey()) {
    coursecfg::save($course->id, optional_param_array('types', [], PARAM_PLUGIN));
    redirect($report, get_string('settingssaved', 'local_alertatemprana'), null, \core\output\notification::NOTIFY_SUCCESS);
}

$PAGE->set_url($url);
$PAGE->set_context($context);
$PAGE->set_pagelayout('report');
$PAGE->set_title(get_string('settings', 'local_alertatemprana') . ': ' . format_string($course->shortname));
$PAGE->set_heading(format_string($course->fullname));
$PAGE->navbar->add(get_string('report', 'local_alertatemprana'), $report);

echo $OUTPUT->header();
echo $OUTPUT->heading(get_string('settings', 'local_alertatemprana'));
echo html_writer::tag('p', get_string('settingsintro', 'local_alertatemprana'));
echo html_writer::tag('p', get_string('settingsadvice', 'local_alertatemprana'), ['class' => 'text-muted']);

$available = coursecfg::available($course->id);
$chosen = coursecfg::types($course->id);
echo html_writer::start_tag('form', ['method' => 'post', 'action' => $url]);
echo html_writer::empty_tag('input', ['type' => 'hidden', 'name' => 'sesskey', 'value' => sesskey()]);
$table = new html_table();
$table->attributes['class'] = 'generaltable';
$table->head = ['', get_string('settingstype', 'local_alertatemprana'), get_string('settingscount', 'local_alertatemprana'), ''];
foreach (array_unique(array_merge([coursecfg::ALWAYS], array_keys($available))) as $type) {
    $always = $type === coursecfg::ALWAYS;
    $dated = in_array($type, coursecfg::DATED);
    $attrs = ['type' => 'checkbox', 'name' => 'types[]', 'value' => $type, 'id' => "type_$type"];
    if (in_array($type, $chosen) || $always) {
        $attrs['checked'] = 'checked';
    }
    if ($always || !$dated) {
        $attrs['disabled'] = 'disabled';
    }
    $note = $always ? get_string('settingsalways', 'local_alertatemprana')
        : ($dated ? '' : get_string('settingsnodate', 'local_alertatemprana'));
    $table->data[] = [html_writer::empty_tag('input', $attrs),
        html_writer::label(get_string('modulenameplural', $type), "type_$type"),
        $available[$type] ?? 0, html_writer::tag('span', $note, ['class' => 'text-muted small'])];
}
echo html_writer::table($table);
echo html_writer::tag('button', get_string('savechanges'), ['type' => 'submit', 'class' => 'btn btn-primary']);
echo ' ' . html_writer::link($report, get_string('cancel'), ['class' => 'btn btn-secondary']);
echo html_writer::end_tag('form');
echo $OUTPUT->footer();
