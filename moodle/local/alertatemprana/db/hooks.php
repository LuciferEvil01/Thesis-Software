<?php
defined('MOODLE_INTERNAL') || die();

// Aviso de alerta temprana en la página principal del curso, para los profesores (P22).
$callbacks = [
    [
        'hook' => \core\hook\output\before_http_headers::class,
        'callback' => [\local_alertatemprana\hook_callbacks::class, 'course_banner'],
    ],
];
