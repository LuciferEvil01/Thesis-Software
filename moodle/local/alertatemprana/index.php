<?php
// Informe de alerta temprana de un curso: la predicción más reciente, su historial y el botón para
// pedir una nueva (como report/insights; P12).
require_once(__DIR__ . '/../../config.php');
require_once(__DIR__ . '/lib.php');

use local_alertatemprana\actions;
use local_alertatemprana\requests;

$courseid = required_param('id', PARAM_INT);
$runid = optional_param('runid', 0, PARAM_INT);
$all = optional_param('all', 0, PARAM_BOOL);
$course = get_course($courseid);
require_login($course);
$context = context_course::instance($course->id);
require_capability('local/alertatemprana:view', $context);

$runs = $DB->get_records('local_alertatemprana_run', ['courseid' => $course->id], 'timecreated DESC, id DESC');
if (!isset($runs[$runid])) {
    $runid = $runs ? array_key_first($runs) : 0;
}
$url = new moodle_url('/local/alertatemprana/index.php', ['id' => $course->id, 'runid' => $runid, 'all' => $all]);
$PAGE->set_url($url);
$PAGE->set_context($context);
$PAGE->set_pagelayout('report');
$PAGE->set_title(get_string('report', 'local_alertatemprana') . ': ' . format_string($course->shortname));
$PAGE->set_heading(format_string($course->fullname));

echo $OUTPUT->header();
echo $OUTPUT->heading(get_string('report', 'local_alertatemprana'));

// Panel de control (P20, P21): estado de la última solicitud, botón para pedir una predicción,
// interruptor de los cuestionarios y aviso de las tareas que no se califican de 2 a 5
$pending = requests::pending($course->id);
if ($pending) {
    echo $OUTPUT->notification(get_string('requestpending', 'local_alertatemprana',
        userdate($pending->timecreated, get_string('strftimedatetimeshort'))), 'info');
} else {
    $last = requests::last_teacher_result($course->id);
    if ($last && $last->message !== '' && (!$runs || $last->timeprocessed >= reset($runs)->timecreated)) {
        echo $OUTPUT->notification(s($last->message), 'info');
    }
}
echo html_writer::start_div('card mb-4', ['id' => 'alertatemprana-panel']);
echo html_writer::start_div('card-body');
echo html_writer::tag('h5', get_string('panel', 'local_alertatemprana'), ['class' => 'card-title']);

echo html_writer::start_tag('form', ['method' => 'post', 'action' => new moodle_url('/local/alertatemprana/request.php'),
    'class' => 'mb-3']);
echo html_writer::empty_tag('input', ['type' => 'hidden', 'name' => 'id', 'value' => $course->id]);
echo html_writer::empty_tag('input', ['type' => 'hidden', 'name' => 'sesskey', 'value' => sesskey()]);
echo html_writer::tag('button', get_string('requestnow', 'local_alertatemprana'),
    ['type' => 'submit', 'class' => 'btn btn-primary', 'disabled' => $pending ? 'disabled' : null]);
echo html_writer::tag('span', get_string('requesthelp', 'local_alertatemprana'), ['class' => 'text-muted small ms-2']);
echo html_writer::end_tag('form');

// Interruptor de los cuestionarios: se guarda al pulsarlo
$quizzes = \local_alertatemprana\coursecfg::quizzes($course->id);
echo html_writer::start_tag('form', ['method' => 'post', 'action' => new moodle_url('/local/alertatemprana/evaluations.php'),
    'class' => 'mb-1']);
echo html_writer::empty_tag('input', ['type' => 'hidden', 'name' => 'id', 'value' => $course->id]);
echo html_writer::empty_tag('input', ['type' => 'hidden', 'name' => 'sesskey', 'value' => sesskey()]);
echo html_writer::empty_tag('input', ['type' => 'hidden', 'name' => 'quizzes', 'value' => 0]);
echo html_writer::start_div('form-check form-switch');
echo html_writer::empty_tag('input', ['type' => 'checkbox', 'class' => 'form-check-input', 'role' => 'switch',
    'id' => 'alertatemprana-quizzes', 'name' => 'quizzes', 'value' => 1, 'checked' => $quizzes ? 'checked' : null,
    'onchange' => 'this.form.submit()']);
echo html_writer::label(get_string('quizzes', 'local_alertatemprana'), 'alertatemprana-quizzes', true,
    ['class' => 'form-check-label']);
echo html_writer::end_div();
echo html_writer::tag('noscript', html_writer::tag('button', get_string('savechanges'),
    ['type' => 'submit', 'class' => 'btn btn-secondary btn-sm mt-1']));
echo html_writer::end_tag('form');
echo html_writer::tag('p', get_string('quizzeshelp', 'local_alertatemprana'), ['class' => 'text-muted small mb-0']);

$outofscale = \local_alertatemprana\coursecfg::out_of_scale($course->id);
if ($outofscale) {
    echo html_writer::div(get_string('outofscale', 'local_alertatemprana', implode(', ', $outofscale)),
        'alert alert-warning mt-3 mb-0');
}
echo html_writer::end_div();
echo html_writer::end_div();

if (!$runs) {
    echo $OUTPUT->notification(get_string('noruns', 'local_alertatemprana'), 'info');
    echo $OUTPUT->footer();
    exit;
}

// Historial: cada predicción publicada, la elegida resaltada
$history = new html_table();
$history->attributes['class'] = 'generaltable table-sm mb-4';
$history->head = [get_string('date'), get_string('reason', 'local_alertatemprana'),
    get_string('anchor', 'local_alertatemprana'), get_string('flaggedcol', 'local_alertatemprana')];
foreach ($runs as $r) {
    $label = userdate($r->timecreated, get_string('strftimedatetimeshort'));
    $cell = $r->id == $runid ? html_writer::tag('strong', $label) : html_writer::link(new moodle_url($url, ['runid' => $r->id]), $label);
    $n = $DB->count_records('local_alertatemprana_pred', ['runid' => $r->id]);
    $f = $DB->count_records('local_alertatemprana_pred', ['runid' => $r->id, 'prediction' => 1]);
    $history->data[] = [$cell, local_alertatemprana_reason($r), local_alertatemprana_anchor_name($r), "$f / $n"];
}
echo $OUTPUT->heading(get_string('history', 'local_alertatemprana'), 4);
echo html_writer::table($history);

$run = $runs[$runid];
$preds = $DB->get_records('local_alertatemprana_pred', ['runid' => $run->id], 'predictionscore DESC');
$flagged = array_filter($preds, fn($p) => $p->prediction);
$status = actions::latest_status(array_keys($preds));
$a = (object)['flagged' => count($flagged), 'total' => count($preds), 'day' => $run->cutoffday,
    'date' => userdate($run->timeend, get_string('strftimedate')), 'model' => s($run->modelversion),
    'threshold' => local_alertatemprana_num($run->threshold * 100, 0),
    'evaluation' => local_alertatemprana_anchor_name($run), 'reason' => local_alertatemprana_reason($run)];
echo $OUTPUT->heading(get_string('runheading', 'local_alertatemprana',
    userdate($run->timecreated, get_string('strftimedatetimeshort'))), 4);
echo html_writer::tag('p', get_string('runsummary', 'local_alertatemprana', $a));
echo html_writer::tag('p', get_string('runhelp', 'local_alertatemprana'), ['class' => 'text-muted small']);

$toggle = new moodle_url($url, ['all' => $all ? 0 : 1]);
echo html_writer::link($toggle, get_string($all ? 'showflagged' : 'showall', 'local_alertatemprana'),
    ['class' => 'btn btn-secondary btn-sm mb-3']);

$shown = $all ? $preds : $flagged;
if (!$shown) {
    echo $OUTPUT->notification(get_string('noflagged', 'local_alertatemprana'), 'success');
    echo $OUTPUT->footer();
    exit;
}
$users = user_get_users_by_id(array_map(fn($p) => $p->userid, $shown));

echo html_writer::start_tag('form', ['method' => 'post', 'action' => new moodle_url('/local/alertatemprana/message.php')]);
echo html_writer::empty_tag('input', ['type' => 'hidden', 'name' => 'id', 'value' => $course->id]);
echo html_writer::empty_tag('input', ['type' => 'hidden', 'name' => 'runid', 'value' => $run->id]);
echo html_writer::empty_tag('input', ['type' => 'hidden', 'name' => 'sesskey', 'value' => sesskey()]);

$table = new html_table();
$table->attributes['class'] = 'generaltable table-sm';
$first = local_alertatemprana_calculations(reset($shown))['valores'] ?? [];
$scale = local_alertatemprana_scale($first['escala'] ?? null);
$table->head = ['', get_string('student', 'local_alertatemprana'), get_string('probability', 'local_alertatemprana'),
    get_string('meangrade', 'local_alertatemprana') . $scale, get_string('lastgrade', 'local_alertatemprana') . $scale,
    get_string('recentactivity', 'local_alertatemprana'), get_string('submissions', 'local_alertatemprana'),
    get_string('status', 'local_alertatemprana'), get_string('actions', 'local_alertatemprana')];
$returnurl = $url->out_as_local_url(false);
foreach ($shown as $p) {
    $u = $users[$p->userid];
    $v = local_alertatemprana_calculations($p)['valores'] ?? [];
    $badge = $p->prediction ? html_writer::span(get_string('atrisk', 'local_alertatemprana'), 'badge bg-danger ms-1') : '';
    $st = isset($status[$p->id]) ? html_writer::span(get_string('action_' . $status[$p->id], 'local_alertatemprana'),
        'badge bg-secondary') : html_writer::span(get_string('pending', 'local_alertatemprana'), 'text-muted');
    $act = function (string $action, string $icon) use ($p, $returnurl) {
        global $OUTPUT;
        $link = new moodle_url('/local/alertatemprana/action.php', ['predictionid' => $p->id, 'action' => $action,
            'sesskey' => sesskey(), 'returnurl' => $returnurl]);
        $label = get_string('action_' . $action, 'local_alertatemprana');
        return $OUTPUT->action_icon($link, new pix_icon($icon, $label));
    };
    $details = $OUTPUT->action_icon(new moodle_url('/local/alertatemprana/prediction.php', ['id' => $p->id]),
        new pix_icon('t/preview', get_string('action_predictiondetails', 'local_alertatemprana')));
    $outline = $OUTPUT->action_icon(new moodle_url('/report/outline/user.php',
        ['id' => $p->userid, 'course' => $course->id, 'mode' => 'outline']),
        new pix_icon('i/report', get_string('outlinereport')), null, ['target' => '_blank']);
    $table->data[] = [
        html_writer::checkbox('predictionids[]', $p->id, false, '', ['aria-label' => fullname($u)]),
        $OUTPUT->user_picture($u, ['size' => 24, 'courseid' => $course->id]) . ' ' .
            html_writer::link(new moodle_url('/user/view.php', ['id' => $u->id, 'course' => $course->id]), fullname($u)) . $badge,
        local_alertatemprana_num($p->predictionscore * 100, 0) . ' %',
        local_alertatemprana_grade($v['nota_media'] ?? null),
        array_key_exists('ultima_nota', $v) ? local_alertatemprana_grade($v['ultima_nota']) : '–',
        ($v['eventos_28d'] ?? '–') . ' · ' . get_string('percentileshort', 'local_alertatemprana',
            local_alertatemprana_num(($v['pct_actividad_reciente'] ?? 0) * 100, 0)),
        local_alertatemprana_num(($v['tasa_entrega'] ?? 0) * 100, 0) . ' %',
        $st,
        $details . $outline . $act(actions::SEND_MESSAGE, 't/message') . $act(actions::FIXED, 't/check') .
            $act(actions::NOT_APPLICABLE, 'i/marker') . $act(actions::INCORRECTLY_FLAGGED, 'i/incorrect'),
    ];
}
echo html_writer::table($table);
echo html_writer::tag('button', get_string('messageselected', 'local_alertatemprana'),
    ['type' => 'submit', 'class' => 'btn btn-primary']);
echo html_writer::end_tag('form');
echo $OUTPUT->footer();
