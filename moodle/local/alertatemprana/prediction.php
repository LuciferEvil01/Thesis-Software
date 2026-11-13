<?php
// Detalles de una predicción: qué variables llevaron a la alerta (como report/insights/prediction.php).
require_once(__DIR__ . '/../../config.php');
require_once(__DIR__ . '/lib.php');

use local_alertatemprana\actions;

$id = required_param('id', PARAM_INT);
$pred = $DB->get_record('local_alertatemprana_pred', ['id' => $id], '*', MUST_EXIST);
$run = $DB->get_record('local_alertatemprana_run', ['id' => $pred->runid], '*', MUST_EXIST);
$course = get_course($pred->courseid);
require_login($course);
$context = context_course::instance($course->id);
require_capability('local/alertatemprana:view', $context);
actions::record($pred->id, $USER->id, actions::VIEW_DETAILS);

$student = core_user::get_user($pred->userid, '*', MUST_EXIST);
$PAGE->set_url(new moodle_url('/local/alertatemprana/prediction.php', ['id' => $id]));
$PAGE->set_context($context);
$PAGE->set_pagelayout('report');
$PAGE->set_title(get_string('details', 'local_alertatemprana'));
$PAGE->set_heading(format_string($course->fullname));
$back = new moodle_url('/local/alertatemprana/index.php', ['id' => $course->id, 'runid' => $run->id]);
$PAGE->navbar->add(get_string('report', 'local_alertatemprana'), $back);

echo $OUTPUT->header();
echo $OUTPUT->heading(fullname($student) . ' · ' . userdate($run->timecreated, get_string('strftimedatetimeshort')));
$a = (object)['prob' => local_alertatemprana_num($pred->predictionscore * 100, 0),
    'threshold' => local_alertatemprana_num($run->threshold * 100, 0)];
echo $OUTPUT->notification(get_string($pred->prediction ? 'detailsatrisk' : 'detailsnotatrisk', 'local_alertatemprana', $a),
    $pred->prediction ? 'warning' : 'info', false);

$c = local_alertatemprana_calculations($pred);
$scale = local_alertatemprana_scale($c['valores']['escala'] ?? null);
$table = new html_table();
$table->attributes['class'] = 'generaltable';
$table->head = [get_string('variable', 'local_alertatemprana'), get_string('value', 'local_alertatemprana'),
    get_string('effect', 'local_alertatemprana')];
foreach ($c['variables'] ?? [] as $v) {
    $isPct = str_ends_with($v['nombre'], '_pct') || str_ends_with($v['nombre'], '_rate');
    // Las notas, en la escala del curso (`curso`); las predicciones anteriores a P16 solo traen 0–100.
    $value = $isPct ? get_string('percentileshort', 'local_alertatemprana', local_alertatemprana_num($v['valor'] * 100, 0))
        : (array_key_exists('curso', $v) ? local_alertatemprana_grade($v['curso']) . $scale
        : local_alertatemprana_num($v['valor'] * 100, 1));
    $effect = $v['aporte'] > 0.05 ? html_writer::span(get_string('raisesrisk', 'local_alertatemprana'), 'text-danger')
        : ($v['aporte'] < -0.05 ? html_writer::span(get_string('lowersrisk', 'local_alertatemprana'), 'text-success')
        : get_string('neutral', 'local_alertatemprana'));
    $table->data[] = [get_string('var_' . $v['nombre'], 'local_alertatemprana'), $value, $effect];
}
echo html_writer::table($table);
echo html_writer::tag('p', get_string('detailshelp', 'local_alertatemprana'), ['class' => 'text-muted small']);

$returnurl = $PAGE->url->out_as_local_url(false);
foreach ([actions::SEND_MESSAGE, actions::FIXED, actions::NOT_APPLICABLE, actions::INCORRECTLY_FLAGGED,
        actions::USEFUL, actions::NOT_USEFUL] as $action) {
    echo html_writer::link(new moodle_url('/local/alertatemprana/action.php', ['predictionid' => $pred->id,
        'action' => $action, 'sesskey' => sesskey(), 'returnurl' => $returnurl]),
        get_string('action_' . $action, 'local_alertatemprana'), ['class' => 'btn btn-secondary btn-sm me-1']);
}
echo html_writer::link(new moodle_url('/report/outline/user.php', ['id' => $student->id, 'course' => $course->id,
    'mode' => 'outline']), get_string('outlinereport'), ['class' => 'btn btn-link btn-sm', 'target' => '_blank']);
echo $OUTPUT->footer();
