require.config({
    shim: {
        'jquery.cookie': ['jquery'],
        'jquery.form': ['jquery'],
        'jquery.lazyload': ['jquery'],
        'jquery.scountdown': ['jquery']
    },
    paths: {
        'jquery.cookie': 'lib/jquery.cookie',
        'jquery.form': 'lib/jquery.form',
        'jquery.lazyload': 'lib/jquery.lazyload',
        'jquery.scountdown': 'lib/jquery.scountdown'
    }
});

require(['app']);

