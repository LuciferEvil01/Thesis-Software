<?php
defined('MOODLE_INTERNAL') || die();

$capabilities = [
    // Ver el informe de alertas del curso, actuar sobre ellas y recibir la notificación.
    'local/alertatemprana:view' => [
        'captype' => 'read',
        'contextlevel' => CONTEXT_COURSE,
        'riskbitmask' => RISK_PERSONAL,
        'archetypes' => ['editingteacher' => CAP_ALLOW, 'teacher' => CAP_ALLOW, 'manager' => CAP_ALLOW],
    ],
    // Publicar predicciones (lo usa el usuario de servicio, matriculado como profesor).
    'local/alertatemprana:submit' => [
        'captype' => 'write',
        'contextlevel' => CONTEXT_COURSE,
        'riskbitmask' => RISK_PERSONAL,
        'archetypes' => ['editingteacher' => CAP_ALLOW, 'teacher' => CAP_ALLOW, 'manager' => CAP_ALLOW],
    ],
];
