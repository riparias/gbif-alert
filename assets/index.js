import Vue from 'vue'
import Hello from './Hello.vue';

new Vue({
  el: '#app',
  components: {
    Hello
  },
  delimiters: ['[[', ']]'],
  data: {
    message: 'Hello Vue!'
  }
})