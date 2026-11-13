<?php
defined('MOODLE_INTERNAL') || die();

$observers = [
    ['eventname' => '\core\event\course_deleted', 'callback' => '\local_alertatemprana\observer::course_deleted'],
    ['eventname' => '\core\event\user_graded', 'callback' => '\local_alertatemprana\observer::user_graded'],
];
