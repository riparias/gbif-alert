const path = require('path');
const {VueLoaderPlugin} = require('vue-loader');

module.exports = {
    entry: './assets/index.ts',  // path to our input file
    output: {
        filename: 'index-bundle.js',  // output bundle file name
        path: path.resolve(__dirname, './static'),  // path to our Django static directory
    },
    module: {
        rules: [
            {
                test: /\.vue$/,
                loader: 'vue-loader'
            },
            {
                test: /.css$/,
                use: [
                    'vue-style-loader',
                    'css-loader',
                ]
            },
            {
                test: /\.tsx?$/,
                loader: 'ts-loader',
                exclude: /node_modules/,
                options: {
                    //Then there are settings for a ts-loader, which helps load the TypeScript with Vue.
                    //We also specified the appendTsSuffixTo: [/\.vue$/], option to ts-loader in our webpack.config.js file,
                    //which allows TypeScript to process the code extracted from a single file component.
                    //https://github.com/TypeStrong/ts-loader#appendtssuffixto
                    appendTsSuffixTo: [/\.vue$/],
                }
            }
        ]
    },
    plugins: [
        new VueLoaderPlugin()
    ],
    resolve: {
        alias: {
            vue: 'vue/dist/vue.js'
        }
    }
};