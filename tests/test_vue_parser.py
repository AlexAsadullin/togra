from pathlib import Path

from togra.parsers.vue_parser import VueParser


VUE = b"""
<template>
  <div>
    <MyButton :label="title" />
    <my-card>
      <p>x</p>
    </my-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import Helper from './helper';

const title = ref('hi');
function greet(name: string): string {
    return Helper.format(name);
}
</script>
"""


def test_vue_components_and_script(tmp_path: Path):
    helper = tmp_path / "helper.ts"
    helper.write_text("export default {}\n")
    target_dir = tmp_path
    node = VueParser().parse(
        content=VUE,
        rel_path="App.vue",
        project_root=target_dir,
        file_hash="h",
    )
    assert node.meta.lang == "vue"
    assert "MyButton" in node.extras.get("components_used", [])
    assert "my-card" in node.extras.get("components_used", [])
    # External import recorded
    libs = {i.lib for i in node.imports.external}
    assert "vue" in libs
    # Internal import resolved
    internal_names = {i.name: i.source_path for i in node.imports.internal}
    assert internal_names.get("Helper") == "helper.ts"
    # Function captured
    assert "greet" in node.functions
