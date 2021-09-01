import Vue from 'vue'
import Hello from './Hello.vue';

var app = new Vue({
  el: '#app',
  components: {
    Hello
  },
  delimiters: ['[[', ']]'],
  data: {
    message: 'Hello Vue!'
  }
})