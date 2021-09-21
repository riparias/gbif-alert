const path = require('path');
const {VueLoaderPlugin} = require('vue-loader');

module.exports = {
    entry: {
        index: './assets/ts/pages_entry_points/index.ts',
        occurrence_details: './assets/ts/pages_entry_points/occurrence_details.ts'
    },
    output: {
        filename: '[name]-bundle.js',  // output bundle file name
        path: path.resolve(__dirname, './static_global/js'),  // path to our Django static directory
    },
    module: {
        rules: [
            {
                test: /\.vue$/,
                loader: 'vue-loader',
            },
            {
                test: /.css$/,
                use: [
                    'style-loader',
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
            vue: "vue/dist/vue.esm-bundler.js"
        }
    }
};