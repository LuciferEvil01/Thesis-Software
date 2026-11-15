<?php
// Interruptor «Incluir los cuestionarios del curso» del panel del informe (P20): guarda la elección y
// vuelve al informe. Las tareas entran siempre.
require_once(__DIR__ . '/../../config.php');

use local_alertatemprana\coursecfg;

$courseid = required_param('id', PARAM_INT);
$course = get_course($courseid);
require_login($course);
require_sesskey();
$context = context_course::instance($course->id);
require_capability('local/alertatemprana:view', $context);

$include = optional_param('quizzes', 0, PARAM_BOOL);
coursecfg::set_quizzes($course->id, (bool)$include);
redirect(new moodle_url('/local/alertatemprana/index.php', ['id' => $course->id]),
    get_string($include ? 'quizzeson' : 'quizzesoff', 'local_alertatemprana'), null,
    \core\output\notification::NOTIFY_SUCCESS);
