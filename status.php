<?php
header('Content-Type: application/json');

$load = sys_getloadavg();
$cpu_load = $load[0] * 100; 

echo json_encode([
    "status" => "online",
    "cpu_load" => $cpu_load,
    "current_users" => rand(10, 50),
    "max_users" => 200
]);
?>