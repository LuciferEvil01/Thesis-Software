<?php
// Botón «Calcular predicciones ahora» del informe: deja una solicitud para el servicio (P12).
require_once(__DIR__ . '/../../config.php');

use local_alertatemprana\requests;

$courseid = required_param('id', PARAM_INT);
$course = get_course($courseid);
require_login($course);
require_sesskey();
$context = context_course::instance($course->id);
require_capability('local/alertatemprana:view', $context);

requests::enqueue($course->id, requests::TEACHER, $USER->id);
redirect(new moodle_url('/local/alertatemprana/index.php', ['id' => $course->id]),
    get_string('requestqueued', 'local_alertatemprana'), null, \core\output\notification::NOTIFY_SUCCESS);
