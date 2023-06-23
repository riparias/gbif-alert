const path = require('path');
const webpack = require("webpack");
const {VueLoaderPlugin} = require('vue-loader');

module.exports = {
    entry: {
        early_alert: './assets/ts/early_alert.ts'
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
            },
            {
                test: /\.woff(2)?(\?v=[0-9]\.[0-9]\.[0-9])?$/,
                type: 'asset/resource',
                dependency: { not: ['url'] },
            }
        ]
    },
    plugins: [
        new VueLoaderPlugin(),
        new webpack.DefinePlugin({
            "__VUE_OPTIONS_API__": true,
            "__VUE_PROD_DEVTOOLS__": false,
        }),
        // To avoid a warning in console, see https://github.com/intlify/vue-i18n-next/issues/789
        new webpack.DefinePlugin({
            '__VUE_I18N_FULL_INSTALL__': JSON.stringify(true),
            '__VUE_I18N_LEGACY_API__': JSON.stringify(true),
            '__INTLIFY_PROD_DEVTOOLS__': JSON.stringify(true)
        })
    ],
    resolve: {
        extensions: ['.ts', '.js', '.json'],
        alias: {
            vue: "vue/dist/vue.esm-bundler.js"
        }
    },
    stats: {
        errorDetails: true,
    }
};