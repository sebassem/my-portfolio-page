export interface PortfolioItem {
    name: string;
    desc: string;
    cover: string;
    category: string;
    link: string;
}

export const portfolio: PortfolioItem[] = [
    {
        name: 'Portfolio design',
        desc: 'UI design - User research - webflow development',
        cover: 'https://images.pexels.com/photos/1051075/pexels-photo-1051075.jpeg?auto=compress&cs=tinysrgb&w=1260&h=750&dpr=2',
        category: 'web',
        link: 'https://github.com/sebassem'
    },
    {
        name: 'Portfolio design',
        desc: 'UI design - User research - webflow development',
        cover: 'https://images.pexels.com/photos/2303781/pexels-photo-2303781.jpeg?auto=compress&cs=tinysrgb&w=1600',
        category: 'branding',
        link: 'https://example.com/project-2'
    },
    {
        name: 'Portfolio design',
        desc: 'UI design - User research - webflow development',
        cover: 'https://images.pexels.com/photos/441963/pexels-photo-441963.jpeg?auto=compress&cs=tinysrgb&w=1600',
        category: 'mobile',
        link: 'https://example.com/project-3'
    },
    {
        name: 'Portfolio design',
        desc: 'UI design - User research - webflow development',
        cover: 'https://images.pexels.com/photos/245240/pexels-photo-245240.jpeg?auto=compress&cs=tinysrgb&w=1600',
        category: 'web',
        link: 'https://example.com/project-4'
    },
    {
        name: 'Portfolio design',
        desc: 'UI design - User research - webflow development',
        cover: 'https://images.pexels.com/photos/245240/pexels-photo-245240.jpeg?auto=compress&cs=tinysrgb&w=1600',
        category: 'web',
        link: 'https://example.com/project-5'
    },
    {
        name: 'Portfolio design',
        desc: 'UI design - User research - webflow development',
        cover: 'https://images.pexels.com/photos/245240/pexels-photo-245240.jpeg?auto=compress&cs=tinysrgb&w=1600',
        category: 'web',
        link: 'https://example.com/project-6'
    },
    {
        name: 'Portfolio design',
        desc: 'UI design - User research - webflow development',
        cover: 'https://images.pexels.com/photos/245240/pexels-photo-245240.jpeg?auto=compress&cs=tinysrgb&w=1600',
        category: 'web',
        link: 'https://example.com/project-7'
    },
];

export const tabs = ['all', 'web', 'branding', 'mobile'];
