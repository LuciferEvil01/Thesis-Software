<?php
// Sistema de alerta temprana de estudiantes en riesgo académico (tesis, MatCom, Universidad de La Habana).
defined('MOODLE_INTERNAL') || die();

$plugin->component = 'local_alertatemprana';
$plugin->version = 2026110501;
$plugin->requires = 2025041400; // Moodle 5.0.
$plugin->maturity = MATURITY_ALPHA;
$plugin->release = '0.7 (P20: el profesor elige qué tipos de evaluación analiza el sistema en su curso)';
