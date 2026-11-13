<?php
// Instala el paquete de idioma (por defecto, es) si falta y lo pone como idioma del sitio. Necesita internet.
define('CLI_SCRIPT', true);
require('/var/www/html/config.php');
$lang = $argv[1] ?? 'es';
get_string_manager()->reset_caches();  // la lista de idiomas puede estar en caché tras copiar un paquete
if (!array_key_exists($lang, get_string_manager()->get_list_of_translations(true))) {
    \core\session\manager::set_user(get_admin());
    $controller = new \tool_langimport\controller();
    try {
        $controller->install_languagepacks([$lang]);
    } catch (\Throwable $e) {
        fwrite(STDERR, "Aviso: no se pudo instalar el idioma {$lang}: {$e->getMessage()}\n");
        exit(0);
    }
    get_string_manager()->reset_caches();
}
if (array_key_exists($lang, get_string_manager()->get_list_of_translations(true))) {
    set_config('lang', $lang);
    echo "Idioma del sitio: {$lang}\n";
}
