<?php
defined('MOODLE_INTERNAL') || die();

$functions = [
    'local_alertatemprana_get_activity' => [
        'classname' => \local_alertatemprana\external\get_activity::class,
        'description' => 'Eventos de participación de los estudiantes de un curso, por estudiante, día del curso y módulo.',
        'type' => 'read',
        'capabilities' => 'report/log:view',
    ],
    'local_alertatemprana_get_gradeitems' => [
        'classname' => \local_alertatemprana\external\get_gradeitems::class,
        'description' => 'Nota mínima, máxima y de aprobado de los ítems de módulo del libro de calificaciones de un curso.',
        'type' => 'read',
        'capabilities' => 'local/alertatemprana:submit',
    ],
    'local_alertatemprana_get_course_config' => [
        'classname' => \local_alertatemprana\external\get_course_config::class,
        'description' => 'Tipos de evaluación que el profesor eligió para que el sistema analice su curso (P20).',
        'type' => 'read',
        'capabilities' => 'local/alertatemprana:submit',
    ],
    'local_alertatemprana_save_predictions' => [
        'classname' => \local_alertatemprana\external\save_predictions::class,
        'description' => 'Publica una predicción de un curso y, si se pide, avisa a sus profesores.',
        'type' => 'write',
        'capabilities' => 'local/alertatemprana:submit',
    ],
    'local_alertatemprana_get_runs' => [
        'classname' => \local_alertatemprana\external\get_runs::class,
        'description' => 'Predicciones ya publicadas de un curso.',
        'type' => 'read',
        'capabilities' => 'local/alertatemprana:submit',
    ],
    'local_alertatemprana_get_requests' => [
        'classname' => \local_alertatemprana\external\get_requests::class,
        'description' => 'Solicitudes de predicción pendientes (notas nuevas o petición del profesor).',
        'type' => 'read',
        'capabilities' => 'local/alertatemprana:submit',
    ],
    'local_alertatemprana_complete_requests' => [
        'classname' => \local_alertatemprana\external\complete_requests::class,
        'description' => 'Marca como atendidas solicitudes de predicción de un curso.',
        'type' => 'write',
        'capabilities' => 'local/alertatemprana:submit',
    ],
    'local_alertatemprana_get_actions' => [
        'classname' => \local_alertatemprana\external\get_actions::class,
        'description' => 'Acciones de los profesores sobre las predicciones de un curso.',
        'type' => 'read',
        'capabilities' => 'local/alertatemprana:submit',
    ],
];
