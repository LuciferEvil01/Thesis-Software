<?php
// Registra la acción de un profesor sobre una predicción y vuelve al informe.
require_once(__DIR__ . '/../../config.php');

use local_alertatemprana\actions;

$predictionid = required_param('predictionid', PARAM_INT);
$action = required_param('action', PARAM_ALPHANUMEXT);
$returnurl = optional_param('returnurl', '', PARAM_LOCALURL);
$pred = $DB->get_record('local_alertatemprana_pred', ['id' => $predictionid], '*', MUST_EXIST);
$course = get_course($pred->courseid);
require_login($course);
require_sesskey();
require_capability('local/alertatemprana:view', context_course::instance($course->id));
actions::record($pred->id, $USER->id, $action);

if ($action === actions::SEND_MESSAGE) {
    redirect(new moodle_url('/message/index.php', ['id' => $pred->userid]));
}
redirect($returnurl ? new moodle_url($returnurl) : new moodle_url('/local/alertatemprana/index.php', ['id' => $course->id]),
    get_string('actionsaved', 'local_alertatemprana'), null, \core\output\notification::NOTIFY_SUCCESS);
