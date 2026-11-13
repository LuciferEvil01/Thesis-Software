<?php
defined('MOODLE_INTERNAL') || die();

$messageproviders = [
    'alerta' => [
        'capability' => 'local/alertatemprana:view',
        'defaults' => [
            'popup' => MESSAGE_PERMITTED + MESSAGE_DEFAULT_ENABLED,
            'email' => MESSAGE_PERMITTED + MESSAGE_DEFAULT_ENABLED,
        ],
    ],
];
